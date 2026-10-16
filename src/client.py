"""Kick.com API client."""

import random
from typing import Optional

import cloudscraper
from loguru import logger


class KickClient:
    """Client for interacting with Kick.com API."""

    BASE_URL = "https://kick.com/api/v2"

    def __init__(self, authorization: str):
        self.authorization = authorization
        self.scraper = cloudscraper.create_scraper()

    def _headers(self) -> dict:
        return {"Authorization": self.authorization}

    def get_channel(self, username: str) -> Optional[dict]:
        """Fetch channel information."""
        try:
            url = f"{self.BASE_URL}/channels/{username}"
            response = self.scraper.get(url)
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching channel {username}: {e}")
            return None

    def send_message(self, chatroom_id: int, content: str) -> bool:
        """Send a message to a chatroom."""
        try:
            url = f"{self.BASE_URL}/messages/send/{chatroom_id}"
            payload = {
                "content": content,
                "type": "message",
                "message_ref": str(random.randint(1000000000000, 9999999999999)),
            }
            self.scraper.post(url, json=payload, headers=self._headers())
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def get_active_prediction(self, username: str) -> Optional[dict]:
        """Return the currently active/open prediction for a channel, if any.

        Kick.com provides a dedicated endpoint:
          GET https://kick.com/api/v2/channels/{username}/predictions/latest
        """
        try:
            url = f"{self.BASE_URL}/channels/{username}/predictions/latest"
            headers = self._headers()
            headers.update({
                "Accept": "application/json",
                "Referer": f"https://kick.com/{username}",
            })
            response = self.scraper.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                body = response.json()
                data = body.get("data", {})
                pred = data.get("prediction")
                user_vote = data.get("user_vote")

                if pred and isinstance(pred, dict):
                    state = str(pred.get("state", "")).upper()
                    outcomes = pred.get("outcomes") or []
                    title = pred.get("title", "Unknown")
                    pred_id = pred.get("id")

                    if state == "ACTIVE" and outcomes:
                        if user_vote:
                            logger.info(
                                f"{username}: Prediction '{title}' (ID: {pred_id}) is ACTIVE but user already voted: {user_vote}"
                            )
                            return None
                        logger.info(
                            f"{username}: Found active prediction '{title}' (ID: {pred_id}) with {len(outcomes)} outcomes"
                        )
                        pred["user_vote"] = None
                        return pred
                    else:
                        logger.debug(
                            f"{username}: Latest prediction '{title}' state is {state} (not ACTIVE)"
                        )
        except Exception as e:
            logger.error(f"Error fetching latest prediction for {username}: {e}")

        return None


    def get_latest_prediction_data(self, username: str) -> Optional[dict]:
        """Fetch raw latest prediction and user_vote data for a channel."""
        try:
            url = f"{self.BASE_URL}/channels/{username}/predictions/latest"
            headers = self._headers()
            headers.update({
                "Accept": "application/json",
                "Referer": f"https://kick.com/{username}",
            })
            response = self.scraper.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                body = response.json()
                data = body.get("data", {})
                pred = data.get("prediction")
                user_vote = data.get("user_vote")
                if pred and isinstance(pred, dict):
                    return {
                        "prediction": pred,
                        "user_vote": user_vote,
                    }
                # If no active pred but we got response, return empty context? 
                return {
                    "prediction": pred,
                    "user_vote": user_vote,
                }
        except Exception as e:
            logger.error(f"Error fetching latest prediction data for {username}: {e}")

        return None

    def get_channel_points(self, username: Optional[str] = None) -> Optional[dict]:
        """Get channel/user points/balance information.
        """
        try:
            # Get prediction data which often contains user context
            if username:
                pred_data = self.get_latest_prediction_data(username)
                if pred_data:
                    # Return combined info
                    return {
                        "prediction_context": pred_data,
                        "username": username,
                        "note": "Points balance not directly exposed via public API; showing context info"
                    }
            # Also return user info
            try:
                headers = self._headers()
                headers.update({"Accept": "application/json", "Referer": "https://kick.com"})
                response = self.scraper.get("https://kick.com/api/v1/user", headers=headers, timeout=10)
                if response.status_code == 200:
                    return response.json()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error fetching channel points: {e}")
        return None

    def set_channel_points(self, username: str, amount: int) -> bool:
        """Set/update channel points for the authenticated user on a channel.
        
        WARNING: This is a speculative implementation. Kick does not expose a public
        REST endpoint to arbitrarily set points - points are earned through watching,
        chat activity, etc. This method tries common patterns in case such an endpoint
        exists or is used by the internal API.
        
        Args:
            username: Channel username
            amount: Target points amount to set
        """
        try:
            headers = self._headers()
            headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Referer": f"https://kick.com/{username}",
                "Origin": "https://kick.com",
            })

            # Try various possible endpoints/patterns
            endpoints = [
                f"{self.BASE_URL}/channels/{username}/points",
                f"{self.BASE_URL}/channels/{username}/viewer/points",
                f"{self.BASE_URL}/users/points",
                f"https://kick.com/api/v1/channels/{username}/points",
            ]

            for url in endpoints:
                try:
                    payloads = [
                        {"amount": amount, "points": amount},
                        {"channel_points": amount},
                        {"balance": amount},
                    ]
                    for payload in payloads:
                        response = self.scraper.post(url, json=payload, headers=headers, timeout=10)
                        if response.status_code in (200, 201, 204):
                            logger.success(f"Successfully set points for {username} to {amount}")
                            return True
                        # If method not allowed, try PUT
                        if response.status_code == 405:
                            response = self.scraper.put(url, json=payload, headers=headers, timeout=10)
                            if response.status_code in (200, 201, 204):
                                logger.success(f"Successfully set points for {username} to {amount}")
                                return True
                except Exception:
                    continue

            logger.warning(f"Could not set points for {username} - endpoint not found or not accessible")
            return False
        except Exception as e:
            logger.error(f"Error setting channel points for {username}: {e}")
            return False

    def update_channel_points(self, username: str, amount_delta: int) -> bool:
        """Update channel points by delta amount (add/subtract)."""
        try:
            # First get current points
            current = self.get_channel_points(username)
            current_amount = 0
            if current:
                # Try to extract current amount
                for key in ["channel_points", "points", "balance"]:
                    if key in current:
                        current_amount = int(current[key])
                        break
                    # Check nested
                    viewer = current.get("viewer") or current.get("user") or {}
                    if isinstance(viewer, dict) and key in viewer:
                        current_amount = int(viewer[key])
                        break
            new_amount = current_amount + amount_delta
            return self.set_channel_points(username, new_amount)
        except Exception as e:
            logger.error(f"Error updating channel points for {username}: {e}")
            return False

    def vote_prediction(self, username: str, prediction_id: str,
                        outcome_id: str, amount: int = 50) -> bool:
        """Vote channel points on a prediction outcome."""
        try:
            url = f"{self.BASE_URL}/channels/{username}/predictions/vote"
            headers = self._headers()
            headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Referer": f"https://kick.com/{username}",
                "Origin": "https://kick.com",
            })

            payload = {
                "amount": amount,
                "outcome_id": outcome_id,
            }
            response = self.scraper.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                return True

            # If 400 (e.g. insufficient points for configured amount), retry with platform min (10)
            if amount > 10 and response.status_code == 400:
                logger.info(
                    f"{username}: Vote with {amount} pts failed (likely balance). Retrying with min (10 pts)..."
                )
                payload["amount"] = 10
                retry_resp = self.scraper.post(url, json=payload, headers=headers, timeout=10)
                if retry_resp.status_code == 200:
                    return True

            logger.warning(
                f"Vote on {username} failed: HTTP {response.status_code} - {response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.error(f"Error voting prediction on {username}: {e}")
            return False
