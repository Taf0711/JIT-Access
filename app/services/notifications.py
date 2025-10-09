"""
Notification service for Slack and email alerts
"""
import httpx
from typing import Optional, Dict, Any
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class SlackNotificationService:
    """Service for sending Slack notifications"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
        self.enabled = bool(self.webhook_url)
    
    async def send_notification(
        self,
        message: str,
        color: str = "#36a64f",  # green by default
        title: Optional[str] = None,
        fields: Optional[list] = None
    ) -> bool:
        """
        Send a notification to Slack
        
        Args:
            message: Main message text
            color: Color for the attachment (hex color)
            title: Optional title for the message
            fields: Optional list of field dicts with 'title' and 'value'
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Slack notifications disabled - no webhook URL configured")
            return False
        
        try:
            payload = {
                "attachments": [{
                    "color": color,
                    "title": title or "JIT Access Notification",
                    "text": message,
                    "footer": "JIT Access & Policy Gateway",
                    "ts": int(__import__('time').time())
                }]
            }
            
            if fields:
                payload["attachments"][0]["fields"] = fields
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
                logger.info(f"Slack notification sent successfully")
                return True
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Slack notification: {e}")
            return False
    
    async def notify_new_request(
        self,
        request_id: int,
        requester_name: str,
        resource_name: str,
        duration_hours: float,
        justification: str,
        is_break_glass: bool = False
    ) -> bool:
        """Notify approvers of a new access request"""
        
        color = "#ff9900" if is_break_glass else "#36a64f"  # Orange for break-glass
        title = "🚨 Break-Glass Access Request" if is_break_glass else "📝 New Access Request"
        
        message = (
            f"*{requester_name}* has requested access to *{resource_name}* "
            f"for *{duration_hours:.1f} hours*"
        )
        
        fields = [
            {"title": "Request ID", "value": f"#{request_id}", "short": True},
            {"title": "Resource", "value": resource_name, "short": True},
            {"title": "Duration", "value": f"{duration_hours:.1f} hours", "short": True},
            {"title": "Type", "value": "Break-Glass" if is_break_glass else "Standard", "short": True},
            {"title": "Justification", "value": justification, "short": False}
        ]
        
        return await self.send_notification(
            message=message,
            color=color,
            title=title,
            fields=fields
        )
    
    async def notify_request_approved(
        self,
        request_id: int,
        requester_name: str,
        approver_name: str,
        resource_name: str,
        is_break_glass: bool = False
    ) -> bool:
        """Notify requester that their request was approved"""
        
        color = "#36a64f"  # Green
        title = "✅ Access Request Approved"
        
        message = (
            f"*{approver_name}* has approved your access request for *{resource_name}*\n"
            f"You can now issue a token for request #{request_id}"
        )
        
        fields = [
            {"title": "Request ID", "value": f"#{request_id}", "short": True},
            {"title": "Approved By", "value": approver_name, "short": True},
            {"title": "Resource", "value": resource_name, "short": False}
        ]
        
        if is_break_glass:
            fields.append({"title": "⚠️ Note", "value": "This is a break-glass access grant", "short": False})
        
        return await self.send_notification(
            message=message,
            color=color,
            title=title,
            fields=fields
        )
    
    async def notify_request_denied(
        self,
        request_id: int,
        requester_name: str,
        denier_name: str,
        resource_name: str,
        denial_reason: str
    ) -> bool:
        """Notify requester that their request was denied"""
        
        color = "#ff0000"  # Red
        title = "❌ Access Request Denied"
        
        message = f"Your access request for *{resource_name}* has been denied"
        
        fields = [
            {"title": "Request ID", "value": f"#{request_id}", "short": True},
            {"title": "Denied By", "value": denier_name, "short": True},
            {"title": "Reason", "value": denial_reason, "short": False}
        ]
        
        return await self.send_notification(
            message=message,
            color=color,
            title=title,
            fields=fields
        )
    
    async def notify_break_glass_activated(
        self,
        request_id: int,
        requester_name: str,
        resource_name: str,
        approvers: list
    ) -> bool:
        """Notify security team of break-glass activation"""
        
        color = "#ff0000"  # Red
        title = "🚨 BREAK-GLASS ACCESS ACTIVATED"
        
        approver_names = ", ".join(approvers)
        message = (
            f"*ALERT:* Break-glass access has been activated!\n"
            f"*Requester:* {requester_name}\n"
            f"*Resource:* {resource_name}\n"
            f"*Approved by:* {approver_names}"
        )
        
        fields = [
            {"title": "Request ID", "value": f"#{request_id}", "short": True},
            {"title": "Severity", "value": "HIGH", "short": True},
            {"title": "Action Required", "value": "Review audit logs immediately", "short": False}
        ]
        
        return await self.send_notification(
            message=message,
            color=color,
            title=title,
            fields=fields
        )
    
    async def notify_token_issued(
        self,
        request_id: int,
        requester_name: str,
        resource_name: str,
        expires_at: str
    ) -> bool:
        """Notify that a token was issued"""
        
        color = "#36a64f"  # Green
        title = "🎫 Access Token Issued"
        
        message = f"Token issued for *{requester_name}* to access *{resource_name}*"
        
        fields = [
            {"title": "Request ID", "value": f"#{request_id}", "short": True},
            {"title": "Expires At", "value": expires_at, "short": True}
        ]
        
        return await self.send_notification(
            message=message,
            color=color,
            title=title,
            fields=fields
        )
    
    async def notify_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a generic alert notification"""
        
        color_map = {
            "critical": "#ff0000",
            "warning": "#ff9900",
            "info": "#36a64f"
        }
        
        color = color_map.get(severity.lower(), "#808080")
        title = f"⚠️ Alert: {alert_type}"
        
        fields = []
        if details:
            for key, value in details.items():
                fields.append({
                    "title": key.replace('_', ' ').title(),
                    "value": str(value),
                    "short": True
                })
        
        return await self.send_notification(
            message=message,
            color=color,
            title=title,
            fields=fields
        )


# Singleton instance
slack_service = SlackNotificationService()

