# Xun-POS - Point of Sale System

Fast and lightweight Point of Sale system.

## Quick Start

### Dependency Installation

Before running the program, install the necessary dependencies:

```bash
pip install -r requirements.txt
```

### Run the Program

```bash
python3 login.py
```

### Default Credentials

- **Username:** `admin`
- **Password:** `password`

**Note:** Change the password after the first login.

## Requirements

- **Operating System:** Linux (Ubuntu, Debian, Fedora, Arch, etc.)
- **Python:** 3.7 or higher

For other dependencies, check the **Dependency Installation** section.

**Important:** This application is NOT compatible with Windows.

## Features

### Main Modules

1. **Point of Sale (POS)** - Main sales interface
2. **Product Management** - Add, edit, and delete products
3. **Reports** - Sales and cash flow reports
4. **Settings** - Business details and adjustments

### User System

**Administrator:**
- Full access to all modules
- User management (create, delete, change passwords)
- Access to reports and settings

**Cashier:**
- Access only to POS and Products
- No access to reports, settings, or user management

## File Structure

```
Xun-POS/
├── login.py           # Authentication system
├── pos_gui.py         # Point of Sale
├── products_gui.py    # Product management
├── reports_gui.py     # Reports
├── settings_gui.py    # Settings
├── products.csv       # Product database
├── sales.csv          # Sales log
├── cash_flow.csv      # Cash flow records
├── .credentials       # Users and passwords
├── settings.json      # Store settings
└── install.sh         # Installation script
```

## User Management (Admin Only)

### Add User
1. Login as admin
2. Select option 5: "Add New User"
3. Enter username and password
4. Select role (admin or cashier)

### Change Password
1. Login as admin
2. Select option 7: "Change Password"
3. Select user
4. Enter new password

### Delete User
1. Login as admin
2. Select option 6: "Delete User"
3. Select user to delete
4. Confirm deletion

## Daily Usage

### For Cashiers
1. Login with cashier credentials
2. Access POS to make sales
3. Manage product inventory as needed

### For Administrators
1. Review sales reports daily
2. Update inventory and prices
3. Manage users and system settings
4. Monitor cash flow

## Security

- Passwords hashed (PBKDF2 with SHA256)
- Role-based access control
- Protection against self-deletion of active user
- Protection of the last administrator user

## Data Files

### products.csv
Format: `barcode,name,price,inventory`

### sales.csv
Format: `timestamp,barcode,name,quantity,unit_price,total_price`

### cash_flow.csv
Format: `timestamp,type,amount,concept`

## Troubleshooting

### Python not found
```bash
# Ubuntu/Debian
sudo apt install python3 python3-tk

# Fedora
sudo dnf install python3 python3-tkinter

# Arch
sudo pacman -S python tk
```

### Permission error
```bash
chmod +x login.py
```

### tkinter not available
```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

## Notes

- CSV files use UTF-8 format
- Dates are in YYYY-MM-DD format (mostly) or locale specific
- The interface is completely in English
- Cash flow movements are automatically recorded with each sale

## System Update

To keep data when updating:
1. Backup .csv files, .credentials, and settings.json
2. Update .py files
3. Restore saved data

## Support

For issues or questions, consult the source code or contact the system administrator.

## License

This project is under the MIT License. For more details, see the [LICENSE](LICENSE) file.

---

**Version:** 1.0.0  
**Last Update:** January 2026
