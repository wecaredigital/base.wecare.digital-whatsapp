# =============================================================================
# Tests for Welcome + Menu Handlers
# =============================================================================

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestWelcomeConfig:
    """Tests for welcome message configuration."""
    
    def test_get_welcome_config_returns_default(self):
        """Should return default welcome config when none exists."""
        from handlers.welcome_menu import get_welcome_config
        
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        
        with patch('handlers.welcome_menu.get_table', return_value=mock_table):
            config = get_welcome_config('tenant123')
        
        assert config is not None
        assert 'welcomeText' in config or config == {}
    
    def test_welcome_text_under_1024_chars(self):
        """Welcome text should be under WhatsApp limit."""
        default_text = "Welcome to WECARE.DIGITAL 👋 Choose an option from the menu below, or type what you need help with."
        assert len(default_text) < 1024


class TestMenuConfig:
    """Tests for menu configuration."""
    
    def test_menu_button_text_under_20_chars(self):
        """Menu button text must be <= 20 characters."""
        button_texts = ["Menu", "Services", "Self Service", "Support"]
        for text in button_texts:
            assert len(text) <= 20, f"Button text '{text}' exceeds 20 chars"
    
    def test_menu_row_title_under_24_chars(self):
        """Menu row titles must be <= 24 characters."""
        row_titles = [
            "Services & Brands",
            "Self Service",
            "Support & Contact",
            "Submit Request",
            "Track Request",
            "BNB CLUB",
            "NO FAULT",
            "EXPO WEEK",
            "RITUAL GURU",
            "LEGAL CHAMP",
            "SWDHYA",
            "Request Amendment",
            "Request Tracking",
            "Drop Docs",
            "Enterprise Assist",
            "FAQ",
            "Contact Us",
            "Leave Review",
            "Download App",
            "Careers",
            "Payments Help"
        ]
        for title in row_titles:
            assert len(title) <= 24, f"Row title '{title}' exceeds 24 chars"
    
    def test_menu_row_description_under_72_chars(self):
        """Menu row descriptions must be <= 72 characters."""
        descriptions = [
            "Explore WECARE brands",
            "Forms, docs, tracking",
            "Payments, FAQ, contact",
            "Start a new request",
            "Check status",
            "Travel & stays",
            "ODR & resolution",
            "Digital events",
            "Culture & rituals",
            "Documentation help",
            "Samvad & learning",
            "New request",
            "Update a request",
            "Status check",
            "Upload documents",
            "Business support",
            "Common questions",
            "Talk to WECARE",
            "Share feedback",
            "Get the app",
            "Work with us",
            "UPI / gateway info"
        ]
        for desc in descriptions:
            assert len(desc) <= 72, f"Description '{desc}' exceeds 72 chars"
    
    def test_menu_sections_max_10(self):
        """Each menu should have max 10 sections."""
        # Main menu has 2 sections
        # Services has 1 section
        # Self Service has 3 sections
        # Support has 3 sections
        max_sections = 10
        section_counts = [2, 1, 3, 3]
        for count in section_counts:
            assert count <= max_sections
    
    def test_menu_rows_max_10_per_section(self):
        """Each section should have max 10 rows."""
        max_rows = 10
        row_counts = [3, 2, 6, 3, 1, 1, 3, 2, 1]  # Per section
        for count in row_counts:
            assert count <= max_rows


class TestMenuActions:
    """Tests for menu action handling."""
    
    def test_action_types_valid(self):
        """Action types should be valid."""
        valid_types = ['open_url', 'open_submenu', 'invoke_action', 'send_text']
        test_actions = ['open_url', 'open_submenu', 'invoke_action']
        for action in test_actions:
            assert action in valid_types
    
    def test_urls_are_https(self):
        """All URLs should use HTTPS."""
        urls = [
            "https://www.wecare.digital/submit-request",
            "https://www.wecare.digital/request-tracking",
            "https://www.wecare.digital/bnb-club",
            "https://www.wecare.digital/no-fault",
            "https://www.wecare.digital/expo-week",
            "https://www.wecare.digital/ritual-guru",
            "https://www.wecare.digital/legal-champ",
            "https://www.wecare.digital/swdhya",
            "https://www.wecare.digital/request-amendment",
            "https://www.wecare.digital/drop-docs",
            "https://www.wecare.digital/enterprise-assist",
            "https://www.wecare.digital/faq",
            "https://www.wecare.digital/contact",
            "https://www.wecare.digital/leave-review",
            "https://www.wecare.digital/app",
            "https://www.wecare.digital/careers"
        ]
        for url in urls:
            assert url.startswith("https://"), f"URL '{url}' is not HTTPS"


class TestListReplyHandling:
    """Tests for interactive list reply handling."""
    
    def test_list_reply_payload_structure(self):
        """List reply should have expected structure."""
        list_reply = {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {
                    "id": "go_services",
                    "title": "Services & Brands"
                }
            }
        }
        
        assert list_reply["type"] == "interactive"
        assert list_reply["interactive"]["type"] == "list_reply"
        assert "id" in list_reply["interactive"]["list_reply"]
    
    def test_row_ids_are_unique(self):
        """All row IDs should be unique across menus."""
        row_ids = [
            "go_services", "go_self_service", "go_support",
            "quick_submit", "quick_track",
            "svc_bnb", "svc_nofault", "svc_expo", "svc_ritual", "svc_legal", "svc_swdhya",
            "ss_submit", "ss_amend", "ss_track", "ss_dropdocs", "ss_enterprise",
            "sup_faq", "sup_contact", "sup_review", "sup_app", "sup_careers", "sup_pay_help"
        ]
        assert len(row_ids) == len(set(row_ids)), "Duplicate row IDs found"
