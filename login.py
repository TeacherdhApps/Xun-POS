#!/usr/bin/env python3

import base64
import getpass
import hashlib
import hmac
import os
import platform
import subprocess
import sys


# ANSI Color codes for terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# Prevent execution on Windows OS
if platform.system() == "Windows":
    print("=" * 60)
    print("ERROR: This application is not compatible with Windows")
    print("=" * 60)
    print("\nThis POS system is designed exclusively for Unix systems")
    print("(Linux, macOS, BSD, etc.) and cannot run on Windows.")
    print("\nPlease use a Linux or macOS system to run this application.")
    print("=" * 60)
    sys.exit(1)


class UserManager:
    """Manages user authentication and authorization with secure hashing."""

    def __init__(self, credentials_file=".credentials"):
        self.credentials_file = credentials_file
        self.ensure_credentials_file()

    def ensure_credentials_file(self):
        """Ensure the credentials file exists."""
        if not os.path.exists(self.credentials_file):
            print(
                f"Warning: {self.credentials_file} not found. Creating default admin user."
            )
            self.create_user("admin", "password", "admin", save_now=True)

    def hash_password(self, password, salt=None):
        """Hash a password using pbkdf2_hmac."""
        if salt is None:
            salt = os.urandom(16)
        else:
            if isinstance(salt, str):
                salt = bytes.fromhex(salt)
        
        # 100,000 iterations of SHA256
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return salt.hex() + "$" + pwd_hash.hex()

    def verify_password(self, stored_password, provided_password):
        """Verify a stored password against a provided password."""
        try:
            # Check if it's an old base64 password (no '$' separator and looks like base64)
            if "$" not in stored_password:
                # Attempt to decode as base64 to see if it's a legacy password
                try:
                    decoded = base64.b64decode(stored_password).decode("utf-8")
                    # If successful, compare plaintexts
                    return decoded == provided_password
                except Exception:
                    return False
            
            salt_hex, hash_hex = stored_password.split("$")
            salt = bytes.fromhex(salt_hex)
            pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
            return hmac.compare_digest(pwd_hash.hex(), hash_hex)
        except Exception:
            return False

    def load_users(self):
        """Load all users from the credentials file."""
        users = {}
        try:
            with open(self.credentials_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(":")
                    if len(parts) == 3:
                        username, password_data, role = parts
                        users[username] = {
                            "password": password_data,
                            "role": role,
                        }
        except FileNotFoundError:
            pass
        return users

    def save_users(self, users):
        """Save all users to the credentials file."""
        with open(self.credentials_file, "w") as f:
            for username, data in users.items():
                f.write(f"{username}:{data['password']}:{data['role']}\n")

    def authenticate(self, username, password):
        """Authenticate a user and return their role if successful."""
        users = self.load_users()
        if username in users:
            stored_password = users[username]["password"]
            if self.verify_password(stored_password, password):
                # Check if migration from legacy format is needed
                if "$" not in stored_password:
                    print(f"Migrating password for user '{username}' to secure format...")
                    new_hash = self.hash_password(password)
                    users[username]["password"] = new_hash
                    self.save_users(users)
                
                return users[username]["role"]
        return None

    def create_user(self, username, password, role, save_now=False):
        """Create a new user."""
        users = self.load_users()
        if username in users:
            return False, "User already exists."

        if role not in ["admin", "cashier"]:
            return False, "Invalid role. Must be 'admin' or 'cashier'."

        # Hash the password before saving
        hashed_password = self.hash_password(password)
        users[username] = {"password": hashed_password, "role": role}
        
        if save_now:
            self.save_users(users)
        else:
            # If not saving immediately, we still update the dict, 
            # but usually this method is called when we want to persist.
            self.save_users(users)
            
        return True, "User created successfully."

    def delete_user(self, username):
        """Delete a user."""
        users = self.load_users()
        if username not in users:
            return False, "User not found."

        if (
            username == "admin"
            and len([u for u in users if users[u]["role"] == "admin"]) == 1
        ):
            return False, "Cannot delete the last admin user."

        del users[username]
        self.save_users(users)
        return True, "User deleted successfully."

    def change_password(self, username, new_password):
        """Change a user's password."""
        users = self.load_users()
        if username not in users:
            return False, "User not found."

        users[username]["password"] = self.hash_password(new_password)
        self.save_users(users)
        return True, "Password changed successfully."

    def list_users(self):
        """List all users."""
        users = self.load_users()
        return users


class LoginSystem:
    """Main login system with menu interface."""

    def __init__(self):
        self.user_manager = UserManager()
        self.current_user = None
        self.current_role = None

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system("clear" if os.name != "nt" else "cls")

    def print_header(self, title):
        """Print a formatted header with colors."""
        print("\n" + Colors.BLUE + "╔" + "=" * 68 + "╗" + Colors.RESET)
        print(
            Colors.BLUE
            + "║"
            + Colors.RESET
            + Colors.BOLD
            + Colors.CYAN
            + f"{title:^68}"
            + Colors.RESET
            + Colors.BLUE
            + "║"
            + Colors.RESET
        )
        print(Colors.BLUE + "╚" + "=" * 68 + "╝" + Colors.RESET)

    def print_box(self, content, color=Colors.WHITE):
        """Print content in a box."""
        lines = content.split("\n")
        max_len = max(len(line) for line in lines)

        print(color + "┌" + "─" * (max_len + 2) + "┐" + Colors.RESET)
        for line in lines:
            print(
                color
                + "│"
                + Colors.RESET
                + f" {line:<{max_len}} "
                + color
                + "│"
                + Colors.RESET
            )
        print(color + "└" + "─" * (max_len + 2) + "┘" + Colors.RESET)

    def print_menu_item(self, number, text, icon=""):
        """Print a formatted menu item."""
        print(
            f"  {Colors.BOLD}{Colors.CYAN}{number}.{Colors.RESET} {icon} {Colors.WHITE}{text}{Colors.RESET}"
        )

    def print_section(self, title):
        """Print a section header."""
        print(f"\n{Colors.BOLD}{Colors.YELLOW}{title}{Colors.RESET}")

    def login(self):
        """Handle user login."""
        self.clear_screen()

        # ASCII Art Logo
        print(f"\n{Colors.CYAN}{Colors.BOLD}")
        print("─" * 80)
        print(f"{Colors.BRIGHT_WHITE}{'Xun-POS':^80}{Colors.RESET}")
        print("─" * 80)
        print(f"{Colors.RESET}")
        print(f"{Colors.WHITE}{'Fast, lightweight, Linux-native POS.'.center(80)}{Colors.RESET}")
        print(f"{Colors.RESET}")

        print(
            f"\n{Colors.BRIGHT_WHITE}╔════════════════════════════════════════════════════════════════════╗{Colors.RESET}"
        )
        print(
            f"{Colors.BRIGHT_WHITE}║{Colors.RESET}  {Colors.BOLD}Please enter your credentials     {Colors.RESET}                              {Colors.BRIGHT_WHITE}║{Colors.RESET}"
        )
        print(
            f"{Colors.BRIGHT_WHITE}╚════════════════════════════════════════════════════════════════════╝{Colors.RESET}"
        )

        username = input(f"{Colors.CYAN}Username:{Colors.RESET} ").strip()
        password = getpass.getpass(f"{Colors.CYAN}Password:{Colors.RESET} ")

        role = self.user_manager.authenticate(username, password)

        if role:
            self.current_user = username
            self.current_role = role
            role_display = "Administrator" if role == "admin" else "Cashier"
            print(
                f"\n{Colors.BG_GREEN}{Colors.BOLD} SUCCESS {Colors.RESET} {Colors.GREEN}Login successful!{Colors.RESET}"
            )
            print(
                f"{Colors.BRIGHT_WHITE}Welcome, {Colors.BOLD}{Colors.CYAN}{username}{Colors.RESET} {Colors.BRIGHT_BLACK}({role_display}){Colors.RESET}"
            )
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return True
        else:
            print(
                f"\n{Colors.BG_RED}{Colors.BOLD} ERROR {Colors.RESET} {Colors.RED}Invalid username or password.{Colors.RESET}"
            )
            input(
                f"\n{Colors.YELLOW}Press Enter to try again...{Colors.RESET}"
            )
            return False

    def admin_menu(self):
        """Display and handle admin menu."""
        while True:
            self.clear_screen()

            print(f"\n{Colors.BRIGHT_BLACK}┌{'─' * 68}┐{Colors.RESET}")
            print(
                f"{Colors.BRIGHT_BLACK}│{Colors.RESET} {Colors.BOLD}Active Session:{Colors.RESET} {Colors.CYAN}{self.current_user}{Colors.RESET} {Colors.BRIGHT_BLACK}(Administrator){Colors.RESET}                    {Colors.BRIGHT_BLACK}│{Colors.RESET}"
            )
            print(f"{Colors.BRIGHT_BLACK}└{'─' * 68}┘{Colors.RESET}")

            self.print_section("POS OPERATIONS")
            self.print_menu_item("1", "Point of Sale", "")
            self.print_menu_item("2", "Products", "")
            self.print_menu_item("3", "Reports", "")
            self.print_menu_item("4", "Settings", "")

            self.print_section("USER MANAGEMENT")
            self.print_menu_item("5", "Add New User", "")
            self.print_menu_item("6", "Delete User", "")
            self.print_menu_item("7", "Change Password", "")
            self.print_menu_item("8", "List All Users", "")

            self.print_section("SESSION")
            self.print_menu_item("9", "Logout", "")
            self.print_menu_item("0", "Exit", "")

            choice = input(
                f"\n{Colors.BOLD}{Colors.GREEN}>{Colors.RESET} {Colors.WHITE}Enter your choice:{Colors.RESET} "
            ).strip()

            if choice == "1":
                self.run_python_app("pos_gui.py")
            elif choice == "2":
                self.run_python_app("products_gui.py")
            elif choice == "3":
                self.run_python_app("reports_gui.py")
            elif choice == "4":
                self.run_python_app("settings_gui.py")
            elif choice == "5":
                self.add_user_menu()
            elif choice == "6":
                self.delete_user_menu()
            elif choice == "7":
                self.change_password_menu()
            elif choice == "8":
                self.list_users_menu()
            elif choice == "9":
                print(f"\n{Colors.GREEN}Logged out successfully.{Colors.RESET}")
                input(
                    f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}"
                )
                return
            elif choice == "0":
                print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}")
                sys.exit(0)
            else:
                print(f"\n{Colors.RED}Invalid option.{Colors.RESET}")
                input(
                    f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}"
                )

    def cashier_menu(self):
        """Display and handle cashier menu."""
        while True:
            self.clear_screen()

            print(f"\n{Colors.BRIGHT_BLACK}┌{'─' * 68}┐{Colors.RESET}")
            print(
                f"{Colors.BRIGHT_BLACK}│{Colors.RESET} {Colors.BOLD}Active Session:{Colors.RESET} {Colors.CYAN}{self.current_user}{Colors.RESET} {Colors.BRIGHT_BLACK}(Cashier){Colors.RESET}                            {Colors.BRIGHT_BLACK}│{Colors.RESET}"
            )
            print(f"{Colors.BRIGHT_BLACK}└{'─' * 68}┘{Colors.RESET}")

            self.print_section("AVAILABLE OPERATIONS")
            self.print_menu_item("1", "Point of Sale", "")
            self.print_menu_item("2", "Products", "")

            self.print_section("SESSION")
            self.print_menu_item("3", "Logout", "")
            self.print_menu_item("0", "Exit", "")

            choice = input(
                f"\n{Colors.BOLD}{Colors.GREEN}>{Colors.RESET} {Colors.WHITE}Enter your choice:{Colors.RESET} "
            ).strip()

            if choice == "1":
                self.run_python_app("pos_gui.py")
            elif choice == "2":
                self.run_python_app("products_gui.py")
            elif choice == "3":
                print(f"\n{Colors.GREEN}Logged out successfully.{Colors.RESET}")
                input(
                    f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}"
                )
                return
            elif choice == "0":
                print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}")
                sys.exit(0)
            else:
                print(f"\n{Colors.RED}Invalid option.{Colors.RESET}")
                input(
                    f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}"
                )

    def run_python_app(self, script_name):
        """Run a Python GUI application."""
        if not os.path.exists(script_name):
            print(f"\n{Colors.RED}Error: {script_name} not found.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        try:
            print(f"\n{Colors.CYAN}Starting {script_name}...{Colors.RESET}")
            # Pass user role to pos_gui.py for role-based access control
            if script_name == "pos_gui.py" and self.current_role:
                subprocess.run([sys.executable, script_name, self.current_role])
            else:
                subprocess.run([sys.executable, script_name])
        except Exception as e:
            print(f"\n{Colors.RED}Error executing {script_name}: {e}{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")

    def add_user_menu(self):
        """Menu for adding a new user."""
        self.clear_screen()
        self.print_header("ADD NEW USER")

        print(
            f"\n{Colors.BRIGHT_WHITE}Enter new user details:{Colors.RESET}\n"
        )

        username = input(f"{Colors.CYAN}Username:{Colors.RESET} ").strip()
        if not username:
            print(
                f"\n{Colors.RED}Username cannot be empty.{Colors.RESET}"
            )
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        password = getpass.getpass(f"{Colors.CYAN}Password:{Colors.RESET} ")
        if not password:
            print(f"\n{Colors.RED}Password cannot be empty.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        password_confirm = getpass.getpass(
            f"{Colors.CYAN}Confirm Password:{Colors.RESET} "
        )
        if password != password_confirm:
            print(f"\n{Colors.RED}Passwords do not match.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        print(f"\n{Colors.BOLD}{Colors.YELLOW}Select Role:{Colors.RESET}")
        print(
            f"  {Colors.CYAN}1.{Colors.RESET} Administrator {Colors.BRIGHT_BLACK}(Full Access){Colors.RESET}"
        )
        print(
            f"  {Colors.CYAN}2.{Colors.RESET} Cashier {Colors.BRIGHT_BLACK}(Limited Access){Colors.RESET}"
        )
        role_choice = input(
            f"\n{Colors.GREEN}>{Colors.RESET} Enter choice (1-2): "
        ).strip()

        if role_choice == "1":
            role = "admin"
        elif role_choice == "2":
            role = "cashier"
        else:
            print(f"\n{Colors.RED}Invalid role selection.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        success, message = self.user_manager.create_user(username, password, role)
        if success:
            role_display = "Administrator" if role == "admin" else "Cashier"
            print(
                f"\n{Colors.BG_GREEN}{Colors.BOLD} SUCCESS {Colors.RESET} {Colors.GREEN}{message}{Colors.RESET}"
            )
            print(
                f"{Colors.BRIGHT_WHITE}  User: {Colors.CYAN}{username}{Colors.RESET}"
            )
            print(f"{Colors.BRIGHT_WHITE}  Role: {Colors.CYAN}{role_display}{Colors.RESET}")
        else:
            print(
                f"\n{Colors.BG_RED}{Colors.BOLD} ERROR {Colors.RESET} {Colors.RED}{message}{Colors.RESET}"
            )

        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")

    def delete_user_menu(self):
        """Menu for deleting a user."""
        self.clear_screen()
        self.print_header("DELETE USER")

        users = self.user_manager.list_users()
        if not users:
            print(f"\n{Colors.RED}No users found.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        print(f"\n{Colors.BOLD}{Colors.YELLOW}Current Users:{Colors.RESET}")
        for username, data in users.items():
            role_display = "Administrator" if data["role"] == "admin" else "Cashier"
            print(
                f"  {Colors.CYAN}{username}{Colors.RESET} {Colors.BRIGHT_BLACK}({role_display}){Colors.RESET}"
            )

        username = input(
            f"\n{Colors.GREEN}>{Colors.RESET} Enter username to delete {Colors.BRIGHT_BLACK}(or Press Enter to cancel){Colors.RESET}: "
        ).strip()
        if not username:
            return

        if username == self.current_user:
            print(
                f"\n{Colors.RED}You cannot delete your own account while logged in.{Colors.RESET}"
            )
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        confirm = (
            input(
                f"\n{Colors.YELLOW}WARNING:{Colors.RESET}  Are you sure you want to delete '{Colors.CYAN}{username}{Colors.RESET}'? {Colors.BRIGHT_WHITE}(yes/no):{Colors.RESET} "
            )
            .strip()
            .lower()
        )
        if confirm != "yes":
            print(f"\n{Colors.GREEN}Deletion cancelled.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        success, message = self.user_manager.delete_user(username)
        if success:
            print(
                f"\n{Colors.BG_GREEN}{Colors.BOLD} SUCCESS {Colors.RESET} {Colors.GREEN}{message}{Colors.RESET}"
            )
        else:
            print(
                f"\n{Colors.BG_RED}{Colors.BOLD} ERROR {Colors.RESET} {Colors.RED}{message}{Colors.RESET}"
            )

        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")

    def change_password_menu(self):
        """Menu for changing a user's password."""
        self.clear_screen()
        self.print_header("CHANGE PASSWORD")

        users = self.user_manager.list_users()
        if not users:
            print(f"\n{Colors.RED}No users found.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        print(f"\n{Colors.BOLD}{Colors.YELLOW}Current Users:{Colors.RESET}")
        for username, data in users.items():
            print(f"  {Colors.CYAN}{username}{Colors.RESET}")

        username = input(
            f"\n{Colors.GREEN}>{Colors.RESET} Enter username {Colors.BRIGHT_BLACK}(or Press Enter to cancel){Colors.RESET}: "
        ).strip()
        if not username:
            return

        if username not in users:
            print(f"\n{Colors.RED}User not found.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        new_password = getpass.getpass(
            f"\n{Colors.CYAN}Enter new password:{Colors.RESET} "
        )
        if not new_password:
            print(f"\n{Colors.RED}Password cannot be empty.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        password_confirm = getpass.getpass(
            f"{Colors.CYAN}Confirm new password:{Colors.RESET} "
        )
        if new_password != password_confirm:
            print(f"\n{Colors.RED}Passwords do not match.{Colors.RESET}")
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            return

        success, message = self.user_manager.change_password(username, new_password)
        if success:
            print(
                f"\n{Colors.BG_GREEN}{Colors.BOLD} SUCCESS {Colors.RESET} {Colors.GREEN}{message}{Colors.RESET}"
            )
        else:
            print(
                f"\n{Colors.BG_RED}{Colors.BOLD} ERROR {Colors.RESET} {Colors.RED}{message}{Colors.RESET}"
            )

        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")

    def list_users_menu(self):
        """Menu for listing all users."""
        self.clear_screen()
        self.print_header("LIST USERS")

        users = self.user_manager.list_users()
        if not users:
            print(f"\n{Colors.RED}No users found.{Colors.RESET}")
        else:
            print(
                f"\n{Colors.BOLD}{Colors.CYAN}{'Username':<25} {'Role':<20}{Colors.RESET}"
            )
            print(f"{Colors.BRIGHT_BLACK}{'-' * 45}{Colors.RESET}")
            for username, data in users.items():
                role_display = "Administrator" if data["role"] == "admin" else "Cashier"
                print(
                    f"{Colors.CYAN}{username:<25}{Colors.RESET} {Colors.WHITE}{role_display:<20}{Colors.RESET}"
                )

        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")

    def run(self):
        """Main application loop."""
        while True:
            if self.login():
                if self.current_role == "admin":
                    self.admin_menu()
                elif self.current_role == "cashier":
                    self.cashier_menu()

                # Reset after logout
                self.current_user = None
                self.current_role = None


if __name__ == "__main__":
    try:
        app = LoginSystem()
        app.run()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
