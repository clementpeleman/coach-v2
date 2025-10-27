"""Garmin OAuth2 PKCE authentication service."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from urllib.parse import urlencode
import requests
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import GarminToken, UserProfile
from app.database.database import get_db


class GarminOAuthService:
    """Handles Garmin OAuth2 PKCE authentication flow."""

    # Garmin OAuth2 endpoints
    AUTHORIZATION_URL = "https://connect.garmin.com/oauth2Confirm"
    TOKEN_URL = "https://diauth.garmin.com/di-oauth2-service/oauth/token"
    USER_ID_URL = "https://apis.garmin.com/wellness-api/rest/user/id"
    PERMISSIONS_URL = "https://apis.garmin.com/wellness-api/rest/user/permissions"
    DEREGISTER_URL = "https://apis.garmin.com/wellness-api/rest/user/registration"

    def __init__(self):
        """Initialize Garmin OAuth service."""
        self.client_id = settings.garmin_consumer_key
        self.client_secret = settings.garmin_consumer_secret
        self.fernet = Fernet(settings.encryption_key.encode())

    def generate_code_verifier(self) -> str:
        """
        Generate a cryptographically random code verifier for PKCE.

        Returns:
            A random string between 43 and 128 characters (A-Z, a-z, 0-9, -, ., _, ~)
        """
        # Generate 96 random bytes and encode as base64url (128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(96)).decode('utf-8')
        # Remove padding
        code_verifier = code_verifier.replace('=', '')
        return code_verifier[:128]  # Ensure max 128 characters

    def generate_code_challenge(self, code_verifier: str) -> str:
        """
        Generate code challenge from code verifier using SHA-256.

        Args:
            code_verifier: The code verifier string

        Returns:
            Base64url encoded SHA-256 hash of the code verifier
        """
        # Hash the verifier with SHA-256
        sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        # Encode as base64url
        code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8')
        # Remove padding
        code_challenge = code_challenge.replace('=', '')
        return code_challenge

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        scope: str = "WORKOUT_IMPORT HEALTH_EXPORT ACTIVITY_EXPORT"
    ) -> Tuple[str, str, str]:
        """
        Generate OAuth2 authorization URL for user consent.

        Args:
            redirect_uri: Where to redirect after authorization
            state: Optional state parameter for CSRF protection
            scope: Space-separated list of permission scopes
                   Default: "WORKOUT_IMPORT HEALTH_EXPORT ACTIVITY_EXPORT"

        Returns:
            Tuple of (authorization_url, code_verifier, state)
        """
        # Generate PKCE parameters
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)

        # Generate state if not provided
        if not state:
            state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').replace('=', '')

        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope
        }

        # Construct URL with proper encoding
        param_str = urlencode(params)
        auth_url = f"{self.AUTHORIZATION_URL}?{param_str}"

        return auth_url, code_verifier, state

    def exchange_code_for_token(
        self,
        authorization_code: str,
        code_verifier: str,
        redirect_uri: str
    ) -> Dict:
        """
        Exchange authorization code for access token.

        Args:
            authorization_code: The authorization code from callback
            code_verifier: The code verifier used to generate the challenge
            redirect_uri: Must match the redirect_uri used in authorization

        Returns:
            Dict containing access_token, refresh_token, expires_in, etc.

        Raises:
            Exception: If token exchange fails
        """
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(self.TOKEN_URL, data=payload, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        return response.json()

    def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh an expired access token.

        Args:
            refresh_token: The refresh token

        Returns:
            Dict containing new access_token, refresh_token, expires_in, etc.

        Raises:
            Exception: If token refresh fails
        """
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(self.TOKEN_URL, data=payload, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        return response.json()

    def get_user_id(self, access_token: str) -> str:
        """
        Fetch Garmin API User ID using access token.

        Args:
            access_token: Valid OAuth2 access token

        Returns:
            Garmin User ID string

        Raises:
            Exception: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.get(self.USER_ID_URL, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch user ID: {response.text}")

        data = response.json()
        return data['userId']

    def get_user_permissions(self, access_token: str) -> list:
        """
        Fetch user's granted permissions.

        Args:
            access_token: Valid OAuth2 access token

        Returns:
            List of permission strings

        Raises:
            Exception: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.get(self.PERMISSIONS_URL, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch permissions: {response.text}")

        return response.json()

    def deregister_user(self, access_token: str):
        """
        Delete user registration from Garmin.

        Args:
            access_token: Valid OAuth2 access token

        Raises:
            Exception: If deregistration fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.delete(self.DEREGISTER_URL, headers=headers)

        if response.status_code not in [200, 204]:
            raise Exception(f"Deregistration failed: {response.text}")

    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage."""
        return self.fernet.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token."""
        return self.fernet.decrypt(encrypted_token.encode()).decode()

    def store_tokens(
        self,
        db: Session,
        telegram_user_id: int,
        token_data: Dict
    ) -> GarminToken:
        """
        Store OAuth tokens in database.

        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            token_data: Dict from token exchange/refresh

        Returns:
            Created/updated GarminToken instance
        """
        # First get or create user profile
        user_profile = db.query(UserProfile).filter(
            UserProfile.user_id == telegram_user_id
        ).first()

        if not user_profile:
            user_profile = UserProfile(user_id=telegram_user_id)
            db.add(user_profile)
            db.flush()

        # Get Garmin User ID
        access_token = token_data['access_token']
        garmin_user_id = self.get_user_id(access_token)

        # Update user profile with Garmin User ID
        user_profile.garmin_user_id = garmin_user_id

        # Calculate expiration times
        expires_in = token_data.get('expires_in', 86400)  # Default 24 hours
        refresh_expires_in = token_data.get('refresh_token_expires_in', 7775998)  # ~3 months

        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        refresh_expires_at = datetime.utcnow() + timedelta(seconds=refresh_expires_in)

        # Encrypt tokens
        encrypted_access = self.encrypt_token(token_data['access_token'])
        encrypted_refresh = self.encrypt_token(token_data['refresh_token'])

        # Check if token already exists
        garmin_token = db.query(GarminToken).filter(
            GarminToken.user_id == telegram_user_id
        ).first()

        if garmin_token:
            # Update existing token
            garmin_token.garmin_user_id = garmin_user_id
            garmin_token.access_token = encrypted_access
            garmin_token.refresh_token = encrypted_refresh
            garmin_token.token_type = token_data.get('token_type', 'bearer')
            garmin_token.expires_at = expires_at
            garmin_token.refresh_expires_at = refresh_expires_at
            garmin_token.scope = token_data.get('scope', '')
            garmin_token.updated_at = datetime.utcnow()
        else:
            # Create new token
            garmin_token = GarminToken(
                user_id=telegram_user_id,
                garmin_user_id=garmin_user_id,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_type=token_data.get('token_type', 'bearer'),
                expires_at=expires_at,
                refresh_expires_at=refresh_expires_at,
                scope=token_data.get('scope', '')
            )
            db.add(garmin_token)

        db.commit()
        db.refresh(garmin_token)

        return garmin_token

    def get_valid_access_token(self, db: Session, telegram_user_id: int) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Args:
            db: Database session
            telegram_user_id: Telegram user ID

        Returns:
            Valid access token or None if no token exists

        Raises:
            Exception: If token refresh fails
        """
        garmin_token = db.query(GarminToken).filter(
            GarminToken.user_id == telegram_user_id
        ).first()

        if not garmin_token:
            return None

        # Check if access token is expired (with 10 minute buffer)
        if datetime.utcnow() >= (garmin_token.expires_at - timedelta(minutes=10)):
            # Token is expired or about to expire, refresh it
            encrypted_refresh = garmin_token.refresh_token
            refresh_token = self.decrypt_token(encrypted_refresh)

            # Refresh the token
            new_token_data = self.refresh_access_token(refresh_token)

            # Store the new tokens
            self.store_tokens(db, telegram_user_id, new_token_data)

            return new_token_data['access_token']
        else:
            # Token is still valid
            encrypted_access = garmin_token.access_token
            return self.decrypt_token(encrypted_access)

    def delete_tokens(self, db: Session, telegram_user_id: int):
        """
        Delete stored tokens for a user.

        Args:
            db: Database session
            telegram_user_id: Telegram user ID
        """
        db.query(GarminToken).filter(
            GarminToken.user_id == telegram_user_id
        ).delete()
        db.commit()
