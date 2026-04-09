"""CAPTCHA solver integration for 2Captcha and CapMonster.

Handles reCAPTCHA v2/v3 and hCaptcha token solving.
"""

import asyncio
import time

import aiohttp

from utils.logger import get_logger

log = get_logger("captcha")


class CaptchaSolver:
    """Unified CAPTCHA solving interface."""

    def __init__(self, provider: str, api_key: str):
        self.provider = provider.lower()
        self.api_key = api_key

        if self.provider == "2captcha":
            self.submit_url = "https://2captcha.com/in.php"
            self.result_url = "https://2captcha.com/res.php"
        elif self.provider == "capmonster":
            self.submit_url = "https://api.capmonster.cloud/createTask"
            self.result_url = "https://api.capmonster.cloud/getTaskResult"
        else:
            raise ValueError(f"Unknown CAPTCHA provider: {provider}")

    async def solve_recaptcha_v2(
        self, site_key: str, page_url: str, timeout: int = 120
    ) -> str:
        """Solve a reCAPTCHA v2 challenge.

        Args:
            site_key: The reCAPTCHA site key from the page
            page_url: URL of the page with the CAPTCHA
            timeout: Max seconds to wait for solution

        Returns:
            CAPTCHA token string to inject into the page
        """
        if self.provider == "2captcha":
            return await self._solve_2captcha(
                "userrecaptcha", site_key, page_url, timeout
            )
        else:
            return await self._solve_capmonster(
                "RecaptchaV2TaskProxyless", site_key, page_url, timeout
            )

    async def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "verify", min_score: float = 0.7, timeout: int = 120
    ) -> str:
        """Solve a reCAPTCHA v3 challenge."""
        if self.provider == "2captcha":
            return await self._solve_2captcha(
                "userrecaptcha", site_key, page_url, timeout,
                extra={"version": "v3", "action": action, "min_score": min_score}
            )
        else:
            return await self._solve_capmonster(
                "RecaptchaV3TaskProxyless", site_key, page_url, timeout,
                extra={"pageAction": action, "minScore": min_score}
            )

    async def solve_hcaptcha(
        self, site_key: str, page_url: str, timeout: int = 120
    ) -> str:
        """Solve an hCaptcha challenge."""
        if self.provider == "2captcha":
            return await self._solve_2captcha(
                "hcaptcha", site_key, page_url, timeout
            )
        else:
            return await self._solve_capmonster(
                "HCaptchaTaskProxyless", site_key, page_url, timeout
            )

    async def _solve_2captcha(
        self, method: str, site_key: str, page_url: str, timeout: int, extra: dict = None
    ) -> str:
        """Submit and poll 2Captcha API."""
        params = {
            "key": self.api_key,
            "method": method,
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }
        if extra:
            params.update(extra)

        async with aiohttp.ClientSession() as session:
            # Submit task
            async with session.post(self.submit_url, data=params) as resp:
                data = await resp.json()
                if data.get("status") != 1:
                    raise CaptchaError(f"2Captcha submit failed: {data}")
                task_id = data["request"]

            log.info(f"2Captcha task submitted: {task_id}")

            # Poll for result
            start = time.time()
            while time.time() - start < timeout:
                await asyncio.sleep(5)
                async with session.get(
                    self.result_url,
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == 1:
                        log.info("CAPTCHA solved successfully")
                        return data["request"]
                    if "CAPCHA_NOT_READY" not in str(data.get("request", "")):
                        raise CaptchaError(f"2Captcha error: {data}")

            raise CaptchaError("CAPTCHA solve timed out")

    async def _solve_capmonster(
        self, task_type: str, site_key: str, page_url: str, timeout: int, extra: dict = None
    ) -> str:
        """Submit and poll CapMonster API."""
        task = {
            "type": task_type,
            "websiteURL": page_url,
            "websiteKey": site_key,
        }
        if extra:
            task.update(extra)

        payload = {"clientKey": self.api_key, "task": task}

        async with aiohttp.ClientSession() as session:
            # Submit task
            async with session.post(self.submit_url, json=payload) as resp:
                data = await resp.json()
                if data.get("errorId", 0) != 0:
                    raise CaptchaError(f"CapMonster submit failed: {data}")
                task_id = data["taskId"]

            log.info(f"CapMonster task submitted: {task_id}")

            # Poll for result
            start = time.time()
            while time.time() - start < timeout:
                await asyncio.sleep(3)
                async with session.post(
                    self.result_url,
                    json={"clientKey": self.api_key, "taskId": task_id},
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == "ready":
                        token = data["solution"].get(
                            "gRecaptchaResponse",
                            data["solution"].get("token", ""),
                        )
                        log.info("CAPTCHA solved successfully")
                        return token
                    if data.get("errorId", 0) != 0:
                        raise CaptchaError(f"CapMonster error: {data}")

            raise CaptchaError("CAPTCHA solve timed out")

    def inject_token(self, driver, token: str, callback_name: str = None):
        """Inject a solved CAPTCHA token into the Selenium page.

        Args:
            driver: Selenium WebDriver
            token: Solved CAPTCHA token
            callback_name: Optional JS callback function name
        """
        driver.execute_script(f"""
            document.getElementById('g-recaptcha-response').innerHTML = '{token}';
            // Also try textarea variant
            var textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"]');
            textareas.forEach(function(ta) {{ ta.innerHTML = '{token}'; }});
        """)

        if callback_name:
            driver.execute_script(f"{callback_name}('{token}');")


class CaptchaError(Exception):
    """Raised when CAPTCHA solving fails."""
    pass
