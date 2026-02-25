import logging
import time

import httpx

from backend.config import SOLANA_RPC_URL

logger = logging.getLogger(__name__)

DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


class SolanaTxHelper:

    def __init__(self, rpc_url: str | None = None):
        self.rpc_url = rpc_url or SOLANA_RPC_URL or DEFAULT_RPC
        logger.info("SolanaTxHelper using RPC: %s", self.rpc_url[:40])

    def _rpc_call(self, method: str, params: list | None = None) -> dict:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(self.rpc_url, json=body)
            resp.raise_for_status()
            return resp.json()

    def sign_and_send(self, tx_bytes: bytes) -> str:
        try:
            import base64
            encoded = base64.b64encode(tx_bytes).decode()
            result = self._rpc_call("sendTransaction", [encoded, {"encoding": "base64"}])

            if "error" in result:
                err = result["error"]
                logger.error("Solana sendTransaction error: %s", err)
                return f"error:{err.get('message', str(err))}"

            tx_sig = result.get("result", "")
            logger.info("Solana TX sent: %s", tx_sig)
            return tx_sig
        except Exception as exc:
            logger.error("Solana sign_and_send error: %s", exc, exc_info=True)
            return f"error:{exc}"

    def confirm_tx(self, signature: str, timeout: int = 30) -> bool:
        try:
            deadline = time.time() + timeout
            while time.time() < deadline:
                result = self._rpc_call("getSignatureStatuses", [[signature]])
                statuses = result.get("result", {}).get("value", [])
                if statuses and statuses[0] is not None:
                    status = statuses[0]
                    if status.get("confirmationStatus") in ("confirmed", "finalized"):
                        logger.info("Solana TX confirmed: %s", signature)
                        return True
                    if status.get("err"):
                        logger.error("Solana TX failed: %s err=%s", signature, status["err"])
                        return False
                time.sleep(2)

            logger.warning("Solana TX confirmation timeout: %s", signature)
            return False
        except Exception as exc:
            logger.error("Solana confirm_tx error: %s", exc, exc_info=True)
            return False

    def get_balance(self, pubkey: str) -> float:
        try:
            result = self._rpc_call("getBalance", [pubkey])
            lamports = result.get("result", {}).get("value", 0)
            sol = lamports / 1e9
            logger.info("Solana balance for %s: %.6f SOL", pubkey[:12], sol)
            return sol
        except Exception as exc:
            logger.error("Solana get_balance error: %s", exc, exc_info=True)
            return 0.0
