#!/usr/bin/env python3
import os
from playwright.sync_api import sync_playwright, TimeoutError, Error as PlaywrightError
from typing import Dict, Any, List, Optional
import json

# Global quiet mode flag (set by CLI)
QUIET_MODE = False

def log(message: str):
    """Print message only if not in quiet mode."""
    if not QUIET_MODE:
        print(message)

class CarrierAutomation:
    """
    Browser automation tool for carrier.relayondemand.com with simple interface for models.
    Designed to be used by small/dumb LLMs without deep technical knowledge.
    """

    def __init__(self, quiet=False):
        # Initialize environment variables from .env file
        self.username = os.getenv('CARRIER_USERNAME', 'apitest@test.com')
        self.password = os.getenv('CARRIER_PASSWORD', 'test123')
        self.browser_context: Optional[Any] = None
        self.page: Optional[Any] = None
        self.browser: Optional[Any] = None
        self.playwright = None
        self.quiet = quiet

    def setup_browser(self, headless=True):
        """
        Initialize the Playwright browser with persistent storage.
        Uses full Chromium with --headless=new for proper Angular SPA rendering.
        """
        log(f"Initializing browser (headless={headless})...")
        self.playwright = sync_playwright().start()
        user_data_dir = os.path.expanduser('~/.carrier_automation_storage')
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)

        # Create browser context with persistent storage
        try:
            # Use full Chromium with --headless=new for proper SPA rendering
            # The headless shell doesn't render Angular apps correctly
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--disable-gpu',
            ]
            if headless:
                launch_args.append('--headless=new')

            self.browser = self.playwright.chromium.launch(
                headless=False,  # We handle headless via --headless=new arg
                args=launch_args
            )

            # Create context with storage state for session persistence
            storage_state_path = os.path.join(user_data_dir, 'storage_state.json')
            if os.path.exists(storage_state_path):
                self.browser_context = self.browser.new_context(
                    storage_state=storage_state_path,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    ignore_https_errors=True,
                    viewport={'width': 1920, 'height': 1080}
                )
            else:
                self.browser_context = self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    ignore_https_errors=True,
                    viewport={'width': 1920, 'height': 1080}
                )

            self.page = self.browser_context.new_page()

            # Block problematic resources
            self.page.route("**/*.{png,jpg,jpeg,gif,svg,css}", lambda route: route.continue_())
            def block_scripts(route):
                url = route.request.url
                if "maps.googleapis.com" in url or "pendo.io" in url or "google-analytics.com" in url:
                    route.abort()
                else:
                    route.continue_()
            self.page.route("**/*", block_scripts)

            # Only add console handlers if not in quiet mode
            if not self.quiet:
                self.page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.type}: {msg.text}"))
                self.page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}"))

            self.page.set_viewport_size({"width": 1920, "height": 1080})
            return True
        except Exception as e:
            log(f"Failed to launch browser: {e}")
            return False
    
    def take_screenshot(self, path: str) -> bool:
        """Take a screenshot for debugging."""
        if self.page:
            try:
                self.page.screenshot(path=path, full_page=True)
                return True
            except Exception as e:
                log(f"Screenshot failed: {e}")
        return False

    def search_text(self, text: str) -> List[Dict[str, str]]:
        """Find elements containing specific text and return their selectors/details."""
        if not self.page:
            return []
        
        elements = self.page.query_selector_all(f"text='{text}'")
        results = []
        for el in elements:
            try:
                tag = el.evaluate("el => el.tagName")
                text_content = el.text_content()
                results.append({
                    "tag": tag,
                    "text": text_content.strip(),
                    "id": el.get_attribute("id") or "",
                    "class": el.get_attribute("class") or ""
                })
            except:
                pass
        return results

    def create_dispatch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        High-level method to create a dispatch order.
        Handles mapping of natural language fields to form elements.
        """
        if not self.page:
            return {"success": False, "error": "No browser session"}
            
        try:
            # Navigation is handled by the caller or we can force it here
            # For now assume we are on the right page or need to click 'Create'
            
            # Map of user-friendly names to possible form selectors (heuristic)
            field_mappings = {
                "start_time": ["#startTime", "[name='startTime']", "select:has-text('start')"],
                "start_address": ["#startAddress", "[name='startAddress']", "input[placeholder*='Address']"],
                "duration": ["#duration", "[name='duration']", "select:has-text('how long')"],
                "payment": ["#payment", "[name='paymentType']", "select:has-text('pay')"],
                "additional_notes": ["#additionalNotes", "textarea[placeholder*='Additional']", "[name='notes']"],
                "internal_notes": ["#internalNotes", "textarea[placeholder*='Internal']", "[name='internalNotes']"],
                "trailer_type": ["#trailerType", "input[placeholder*='Trailer']"],
                "endorsements": ["#endorsements", "input[placeholder*='Endorsements']"],
                "unit_numbers": ["#unitNumbers", "input[placeholder*='Unit Numbers']"]
            }
            
            filled_count = 0
            for key, value in data.items():
                if key in field_mappings and value:
                    for selector in field_mappings[key]:
                        try:
                            el = self.page.query_selector(selector)
                            if el:
                                if el.evaluate("el => el.tagName === 'SELECT'"):
                                    el.select_option(label=str(value))
                                else:
                                    el.fill(str(value))
                                filled_count += 1
                                break
                        except:
                            continue
            
            return {
                "success": True, 
                "message": f"Attempted to fill {filled_count} fields",
                "fields_filled": filled_count
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def login(self) -> Dict[str, Any]:
        """
        Perform secure login with stored credentials.
        Returns JSON status and session info.
        - Always performs fresh login to avoid stale session issues.
        """
        try:
            log("Navigating to login page...")
            self.page.goto('https://carrier.relayondemand.com/Carrier/login', timeout=30000)

            # Wait for page to load
            try:
                self.page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            self.page.wait_for_timeout(3000)

            # Check if login form elements exist (more reliable than URL check)
            has_login_form = False
            login_selectors = [
                'input[name="Email"]', 'input[name="username"]',
                'input[type="email"]', '[placeholder="Email"]'
            ]
            for sel in login_selectors:
                try:
                    if self.page.is_visible(sel, timeout=2000):
                        has_login_form = True
                        break
                except:
                    pass

            if not has_login_form:
                # No login form visible - try navigating to a protected page to verify
                log("No login form found, verifying auth by navigating to client/home...")
                self.page.goto('https://carrier.relayondemand.com/Carrier/client/home', timeout=15000)
                try:
                    self.page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    pass
                self.page.wait_for_timeout(3000)

                # Check if we got redirected back to login or got a 401
                current_url = self.page.url.lower()
                if 'login' in current_url:
                    log("Redirected to login - session expired, re-logging in...")
                    self.page.goto('https://carrier.relayondemand.com/Carrier/login', timeout=30000)
                    try:
                        self.page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    self.page.wait_for_timeout(3000)
                else:
                    # Check if form elements loaded (proves we're actually authenticated)
                    try:
                        form_el = self.page.query_selector('input, select, textarea')
                        if form_el:
                            log("Already logged in and authenticated (form elements found).")
                            return {"success": True, "message": "Already logged in"}
                    except:
                        pass
                    # If no form elements, might be blank/unauthorized - re-login
                    log("Page loaded but no form elements - re-logging in...")
                    self.page.goto('https://carrier.relayondemand.com/Carrier/login', timeout=30000)
                    try:
                        self.page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    self.page.wait_for_timeout(3000)

            log("Filling login form...")
            # Try different selectors for username/password - robust against site changes
            selectors = [
                {'username': 'input[name="Email"]', 'password': 'input[name="password"]'},
                {'username': 'input[name="username"]', 'password': 'input[name="password"]'},
                {'username': '#usernameInput', 'password': '#passwordInput'},
                {'username': '[placeholder="Email"]', 'password': '[placeholder="Password"]'},
                {'username': 'input[type="email"]', 'password': 'input[type="password"]'}
            ]

            filled = False
            for selector_set in selectors:
                try:
                    if self.page.is_visible(selector_set['username'], timeout=3000):
                        log(f"Using selectors: {selector_set}")
                        self.page.fill(selector_set['username'], self.username)
                        self.page.wait_for_timeout(200)
                        self.page.fill(selector_set['password'], self.password)
                        self.page.wait_for_timeout(200)
                        filled = True
                        log("Credentials filled successfully")
                        break
                except PlaywrightError as e:
                    log(f"Selector set failed: {selector_set}")
                    pass

            if not filled:
                 # Fallback: Just try to fill whatever looks right
                 try:
                     log("Trying fallback selectors...")
                     self.page.fill('input[type="email"]', self.username)
                     self.page.wait_for_timeout(200)
                     self.page.fill('input[type="password"]', self.password)
                     log("Credentials filled via fallback")
                 except Exception as e:
                     log(f"Fallback failed: {e}")

            # Submit login button (multiple selectors to handle different button types)
            submit_selectors = ['button[type="submit"]', '#loginButton', 'button:has-text("Log In")', 'button:has-text("Login")', 'button:has-text("Sign In")']
            clicked = False
            for selector in submit_selectors:
                try:
                    if self.page.is_visible(selector, timeout=2000):
                        log(f"Clicking submit button: {selector}")
                        try:
                            with self.page.expect_navigation(timeout=8000):
                                self.page.click(selector)
                        except:
                             log("No immediate navigation, waiting...")
                             pass
                        clicked = True
                        break
                except PlaywrightError as e:
                    log(f"Submit selector failed: {selector}")
                    continue

            if not clicked:
                 log("Trying Enter key as fallback...")
                 self.page.keyboard.press("Enter")

            # Wait for navigation
            log("Waiting for navigation...")
            self.page.wait_for_timeout(5000)

            if "login" not in self.page.url.lower():
                log("Login successful!")
                return {"success": True, "message": "Logged in successfully"}
            else:
                 return {"success": False, "message": "Still on login page after attempt"}

        except TimeoutError as e:
            print(f"Login timed out after 30 seconds: {str(e)}")
            return {"success": False, "message": f"Login timeout error: {str(e)}"}
        except Exception as e:
            log(f"Login failed unexpectedly: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def analyze_forms(self) -> Dict[str, Any]:
        """
        Extract all user input forms, fields, dropdowns, optional sections, and buttons.
        Comprehensive analysis for the Carrier dispatch form.
        """
        if not self.page:
            log("Error: No active browser session")
            return {"success": False, "error": "No browser session"}

        forms_data = []
        buttons_data = []
        optional_sections = []

        try:
            # Wait for page to fully load
            self.page.wait_for_timeout(2000)

            # Find the main form
            form = self.page.query_selector('#place-order-frm') or self.page.query_selector('form')
            if not form:
                form = self.page.query_selector('body')

            form_id = form.get_attribute('id') or 'dispatch-form'
            fields = []

            # Get all input elements
            all_inputs = self.page.query_selector_all('input:not([type="hidden"]), select, textarea')

            for element in all_inputs:
                try:
                    tag_name = element.evaluate('el => el.tagName.toLowerCase()')

                    # Get formcontrolname (Angular) or name/id
                    formcontrol = element.get_attribute('formcontrolname')
                    id_attr = element.get_attribute('id')
                    name_attr = element.get_attribute('name')
                    placeholder = element.get_attribute('placeholder')

                    # Find associated label
                    label = ""
                    # Try to find label by walking up DOM and finding previous label
                    try:
                        label = element.evaluate('''el => {
                            let parent = el.parentElement;
                            for (let i = 0; i < 5 && parent; i++) {
                                let lbl = parent.querySelector('label');
                                if (lbl) return lbl.textContent.trim();
                                parent = parent.parentElement;
                            }
                            return "";
                        }''')
                    except:
                        pass

                    field_info = {
                        "formcontrolname": formcontrol,
                        "id": id_attr,
                        "name": name_attr,
                        "label": label,
                        "placeholder": placeholder,
                        "element_type": tag_name,
                        "input_type": element.get_attribute('type') if tag_name == 'input' else tag_name,
                        "required": 'ng-invalid' in (element.get_attribute('class') or ''),
                        "current_value": element.evaluate('el => el.value') or ""
                    }

                    # For select elements, get available options
                    if tag_name == 'select':
                        try:
                            options = element.query_selector_all('option')
                            field_info["options"] = []
                            for opt in options:
                                opt_text = opt.text_content().strip()
                                opt_value = opt.get_attribute('value')
                                if opt_text and opt_text != 'Select':
                                    field_info["options"].append({
                                        "text": opt_text,
                                        "value": opt_value
                                    })
                        except:
                            pass

                    # Determine a friendly field name
                    field_info["field_name"] = formcontrol or id_attr or name_attr or placeholder or label or tag_name

                    fields.append(field_info)

                except Exception as e:
                    log(f"Error processing element: {e}")
                    continue

            # Find optional expandable sections
            optional_divs = self.page.query_selector_all('.optional-div')
            for div in optional_divs:
                try:
                    label_text = div.query_selector('label')
                    if label_text:
                        optional_sections.append({
                            "label": label_text.text_content().strip(),
                            "expanded": False,
                            "selector": ".optional-div"
                        })
                except:
                    pass

            # Find submit/action buttons
            submit_buttons = self.page.query_selector_all('button.assign-driver-btn, button:has-text("Assign a Driver"), button:has-text("Find me a Driver")')
            for btn in submit_buttons:
                try:
                    btn_text = btn.text_content().strip()
                    btn_class = btn.get_attribute('class') or ''
                    if btn_text and 'hidden' not in btn_class.lower() and 'd-none' not in btn_class:
                        buttons_data.append({
                            "text": btn_text,
                            "class": btn_class,
                            "selector": f'button:has-text("{btn_text}")'
                        })
                except:
                    pass

            forms_data.append({
                "form_id": form_id,
                "field_count": len(fields),
                "fields": fields
            })

            return {
                "success": True,
                "forms": forms_data,
                "total_fields": len(fields),
                "optional_sections": optional_sections,
                "action_buttons": buttons_data,
                "instructions": {
                    "required_fields": ["WhenYouWantDriver", "StartAddress", "DriverBookDurations", "DriverPayType"],
                    "optional_fields": ["SpecialNotes", "InternalNotes", "TrailerType", "Endorsements", "UnitNumbers"],
                    "submit_options": ["Assign a Driver", "Find me a Driver"]
                }
            }
        except Exception as e:
            log(f"Form analysis failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def run_workflow(self) -> Dict[str, Any]:
        """
        Full sequence: Setup → Login → Analyze. Returns JSON with status and data.
        """
        # Step 1: Setup browser (persistent)
        setup_result = self.setup_browser(headless=True)
        if not setup_result:
            return {"success": False, "error": "Browser initialization failed"}
        
        # Step 2: Perform login (if not already)
        login_result = self.login()
        if not login_result['success']:
            return login_result
        
        # Navigate to the order form page (client/home has the dispatch form)
        self.page.goto('https://carrier.relayondemand.com/Carrier/client/home')

        # Wait for page to load
        try:
            self.page.wait_for_load_state('networkidle', timeout=10000)
            # Wait for spinner to disappear if present
            try:
                self.page.wait_for_selector('spinner', state='detached', timeout=5000)
            except:
                pass
            # Extra safety wait for SPA rendering
            self.page.wait_for_timeout(3000)
        except:
            pass

        # Step 3: Analyze forms on current page (after login)
        analysis_result = self.analyze_forms()
        
        return {
            "success": True,
            "login_status": login_result['message'],
            "current_url": self.page.url,
            "forms": analysis_result.get('forms'),
            "total_fields": analysis_result.get('total_fields', 0)
        }
    
    def submit_form(self, form_id: str, field_values: Dict[str, str]) -> Dict[str, Any]:
        """
        Fill out and submit a specific form with given values.
        """
        if not self.page:
            log("Error: No active browser session")
            return {"success": False, "message": "No browser session"}
        
        try:
            # Find the form by ID or first available one
            target_form = None
            if form_id:
                target_form = self.page.query_selector(f'#{form_id}') or self.page.query_selector(f'form[name="{form_id}"]')
            
            if not target_form:
                 # Fallback: If only one form exists, use it
                forms = self.page.query_selector_all('form')
                if len(forms) == 1:
                    target_form = forms[0]
            
            if not target_form:
                 # Last resort: body
                 target_form = self.page.query_selector('body')

            # Fill each field with provided value (robust against missing elements)
            filled_fields = []
            for field_name, value in field_values.items():
                try:
                    # Try multiple selectors: formcontrolname (Angular), name, placeholder, id
                    element = target_form.query_selector(f'[formcontrolname="{field_name}"]') or \
                            target_form.query_selector(f'[name="{field_name}"]') or \
                            target_form.query_selector(f'[placeholder*="{field_name}" i]') or \
                            target_form.query_selector(f'#{field_name}') or \
                            target_form.query_selector(f'#{field_name.lower()}')

                    if element:
                        tag_name = element.evaluate('el => el.tagName.toLowerCase()')
                        if tag_name == 'select':
                            # For select elements, try to match by value or label
                            try:
                                element.select_option(value=str(value))
                            except:
                                try:
                                    element.select_option(label=str(value))
                                except:
                                    element.select_option(index=int(value) if str(value).isdigit() else 0)
                        else:
                            element.fill(str(value))
                        filled_fields.append(field_name)
                        log(f"Filled field '{field_name}' with '{value}'")
                    else:
                        log(f"Warning: Field '{field_name}' not found.")
                except PlaywrightError as e:
                    log(f"Field error: {str(e)}. Skipping...")

            # Return success after filling (don't auto-submit)
            return {
                "success": True,
                "message": f"Filled {len(filled_fields)} fields",
                "filled_fields": filled_fields
            }

        except Exception as e:
            log(f"Error submitting form: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def cleanup(self):
        """
        Close browser resources and clean up.
        """
        user_data_dir = os.path.expanduser('~/.carrier_automation_storage')
        storage_state_path = os.path.join(user_data_dir, 'storage_state.json')

        # Save storage state (cookies, localStorage) for persistence
        if self.browser_context:
            try:
                self.browser_context.storage_state(path=storage_state_path)
                self.browser_context.close()
            except PlaywrightError as e:
                pass

        if self.page:
            try:
                self.page.close()
            except PlaywrightError as e:
                pass

        if self.browser:
            try:
                self.browser.close()
            except PlaywrightError as e:
                pass

        # Stop playwright
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass

# For direct execution (standalone mode)
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Carrier Browser Automation Tool")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress debug output (only JSON results)")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: analyze
    parser_analyze = subparsers.add_parser("analyze", help="Login and analyze forms on the dashboard")

    # Command: submit
    parser_submit = subparsers.add_parser("submit", help="Fill and submit a form")
    parser_submit.add_argument("--form-id", type=str, default="", help="ID of the form to submit")
    parser_submit.add_argument("--data", type=str, required=True, help="JSON string of field values")
    parser_submit.add_argument("--click-button", type=str, default="", help="Button text to click after filling (e.g., 'Assign a Driver')")

    # Command: create_dispatch
    parser_dispatch = subparsers.add_parser("create_dispatch", help="Specialized command for dispatch orders")
    parser_dispatch.add_argument("--data", type=str, required=True, help="JSON string of dispatch fields")

    # Command: dump_text
    parser_dump_text = subparsers.add_parser("dump_text", help="Dump all text on the page")

    # Command: dump_links
    parser_dump_links = subparsers.add_parser("dump_links", help="Dump all links and buttons on the page")

    # Command: navigate
    parser_navigate = subparsers.add_parser("navigate", help="Navigate to a specific path and analyze")
    parser_navigate.add_argument("path", type=str, help="The path to navigate to (e.g., /dispatch/create)")

    # Command: click
    parser_click = subparsers.add_parser("click", help="Click an element on the page")
    parser_click.add_argument("selector", type=str, help="CSS selector of the element to click")

    # Command: dump_html
    parser_dump = subparsers.add_parser("dump_html", help="Dump current page HTML for debugging")

    # Command: screenshot
    parser_screenshot = subparsers.add_parser("screenshot", help="Take a screenshot of the current page")
    parser_screenshot.add_argument("path", type=str, help="Path to save the screenshot")

    # Command: search
    parser_search = subparsers.add_parser("search", help="Search for text on the page")
    parser_search.add_argument("query", type=str, help="Text to search for")

    # Command: get_options
    parser_options = subparsers.add_parser("get_options", help="Get dropdown options for a field")
    parser_options.add_argument("field", type=str, help="The formcontrolname of the dropdown field")

    args = parser.parse_args()

    # Set global quiet mode
    QUIET_MODE = args.quiet

    automation = CarrierAutomation(quiet=args.quiet)
    
    try:
        if args.command == "analyze":
            result = automation.run_workflow()
            print(json.dumps(result, indent=2))

        elif args.command == "search":
            if not automation.setup_browser():
                sys.exit(1)
            automation.login()
            automation.page.wait_for_timeout(5000)
            results = automation.search_text(args.query)
            print(json.dumps(results, indent=2))

        elif args.command == "dump_text":
            if not automation.setup_browser():
                sys.exit(1)
            automation.login()
            automation.page.wait_for_timeout(5000)
            text = automation.page.inner_text("body")
            print(text)

        elif args.command == "dump_links":
            if not automation.setup_browser():
                sys.exit(1)
            automation.login()
            automation.page.wait_for_timeout(5000)
            links = automation.page.query_selector_all('a, button')
            results = []
            for link in links:
                try:
                    results.append({
                        "text": link.text_content().strip(),
                        "tag": link.evaluate("el => el.tagName"),
                        "href": link.get_attribute("href") or "",
                        "id": link.get_attribute("id") or "",
                        "class": link.get_attribute("class") or ""
                    })
                except:
                    pass
            print(json.dumps(results, indent=2))

        elif args.command == "navigate":
            if not automation.setup_browser():
                sys.exit(1)
            login_result = automation.login()
            if not login_result['success']:
                print(json.dumps(login_result, indent=2))
                sys.exit(1)
            
            full_url = f"https://carrier.relayondemand.com/Carrier{args.path}"
            log(f"Navigating to {full_url}...")
            automation.page.goto(full_url)
            
            # Wait for page to settle
            try:
                automation.page.wait_for_load_state('networkidle', timeout=10000)
                automation.page.wait_for_selector('spinner', state='detached', timeout=10000)
            except:
                pass
            automation.page.wait_for_timeout(5000)

            # Analyze the new page
            analysis_result = automation.analyze_forms()
            analysis_result['current_url'] = automation.page.url
            print(json.dumps(analysis_result, indent=2))

        elif args.command == "click":
            if not automation.setup_browser():
                sys.exit(1)
            login_result = automation.login()
            if not login_result['success']:
                print(json.dumps(login_result, indent=2))
                sys.exit(1)
            
            log(f"Clicking element with selector: {args.selector}")
            try:
                automation.page.click(args.selector, timeout=10000)
                log("Click successful. Waiting for page to settle...")
                automation.page.wait_for_load_state('networkidle', timeout=10000)
                automation.page.wait_for_timeout(5000)
                # Analyze page after click
                analysis_result = automation.analyze_forms()
                analysis_result['current_url'] = automation.page.url
                print(json.dumps(analysis_result, indent=2))
            except Exception as e:
                print(json.dumps({"success": False, "error": f"Failed to click element: {str(e)}"}, indent=2))
        
        elif args.command == "dump_html":
            if not automation.setup_browser():
                sys.exit(1)
            automation.login()
            try:
                automation.page.wait_for_load_state('networkidle', timeout=10000)
                automation.page.wait_for_selector('spinner', state='detached', timeout=10000)
            except:
                pass
            automation.page.wait_for_timeout(5000)
            content = automation.page.content()
            print(content)

        elif args.command == "screenshot":
            if not automation.setup_browser():
                sys.exit(1)
            automation.login()

            # Navigate to the form page for a meaningful screenshot
            automation.page.goto('https://carrier.relayondemand.com/Carrier/client/home')
            try:
                automation.page.wait_for_load_state('networkidle', timeout=15000)
                automation.page.wait_for_selector('spinner', state='detached', timeout=5000)
            except:
                pass
            # Wait for Angular SPA to fully render
            automation.page.wait_for_timeout(5000)

            if automation.take_screenshot(args.path):
                print(json.dumps({"success": True, "path": args.path}))
            else:
                print(json.dumps({"success": False, "error": "Screenshot failed"}))

        elif args.command == "submit":
            # Ensure browser is setup and logged in first
            automation.setup_browser()
            automation.login()

            # Navigate to the order form page
            automation.page.goto('https://carrier.relayondemand.com/Carrier/client/home')
            try:
                automation.page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            automation.page.wait_for_timeout(3000)

            try:
                data = json.loads(args.data)
                result = automation.submit_form(args.form_id, data)

                # Click submit button if specified
                if args.click_button:
                    try:
                        automation.page.wait_for_timeout(1000)  # Brief pause before clicking
                        btn = automation.page.query_selector(f'button:has-text("{args.click_button}")')
                        if btn:
                            btn.click()
                            automation.page.wait_for_timeout(2000)  # Wait for action
                            result["button_clicked"] = args.click_button
                        else:
                            result["button_error"] = f"Button '{args.click_button}' not found"
                    except Exception as e:
                        result["button_error"] = str(e)

                print(json.dumps(result, indent=2))
            except json.JSONDecodeError:
                print(json.dumps({"success": False, "error": "Invalid JSON data provided"}))

        elif args.command == "create_dispatch":
            if not automation.setup_browser():
                sys.exit(1)
            automation.login()

            try:
                data = json.loads(args.data)
                result = automation.create_dispatch(data)
                print(json.dumps(result, indent=2))
            except json.JSONDecodeError:
                print(json.dumps({"success": False, "error": "Invalid JSON data provided"}))

        elif args.command == "get_options":
            if not automation.setup_browser():
                sys.exit(1)
            login_result = automation.login()
            if not login_result['success']:
                print(json.dumps(login_result, indent=2))
                sys.exit(1)

            # Navigate to client/home if not there
            if '/client/home' not in automation.page.url:
                automation.page.goto('https://carrier.relayondemand.com/Carrier/client/home')
                automation.page.wait_for_timeout(5000)

            # Find the select element by formcontrolname
            try:
                selector = f'select[formcontrolname="{args.field}"]'
                select_el = automation.page.query_selector(selector)

                if select_el:
                    # Click to expand dropdown (sometimes needed to load options)
                    select_el.click()
                    automation.page.wait_for_timeout(500)

                    # Get all options
                    options = select_el.query_selector_all('option')
                    option_list = []
                    for opt in options:
                        text = opt.text_content().strip()
                        value = opt.get_attribute('value')
                        if text and text != 'Select':
                            option_list.append({"text": text, "value": value})

                    print(json.dumps({
                        "success": True,
                        "field": args.field,
                        "options": option_list
                    }, indent=2))
                else:
                    print(json.dumps({
                        "success": False,
                        "error": f"Select field '{args.field}' not found"
                    }, indent=2))
            except Exception as e:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))

        else:
            # Default behavior if no command
            result = automation.run_workflow()
            print(json.dumps(result, indent=2))
            
    finally:
        automation.cleanup()
