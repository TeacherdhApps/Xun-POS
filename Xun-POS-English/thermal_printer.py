import os
from datetime import datetime

class ThermalPrinter:
    def __init__(self, device_path="/dev/thermal_printer"):
        self.ESC = b'\x1b'
        self.GS = b'\x1d'
        self.device_path = device_path
        
        # Auto-detect if configured path does not exist
        if not os.path.exists(self.device_path):
            import glob
            # Look for standard USB printer devices
            found_printers = glob.glob("/dev/usb/lp*")
            if found_printers:
                self.device_path = found_printers[0]
                print(f"Auto-detected printer at: {self.device_path}")
            else:
                print(f"Warning: No printer found at {device_path} and no /dev/usb/lp* devices detected.")

    def _write(self, data):
        try:
            with open(self.device_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            print(f"Error printing to {self.device_path}: {e}")

    def init_printer(self):
        self._write(self.ESC + b'@')

    def set_align(self, align='left'):
        vals = {'left': 0, 'center': 1, 'right': 2}
        n = vals.get(align, 0)
        self._write(self.ESC + b'a' + bytes([n]))

    def set_bold(self, enabled=True):
        n = 1 if enabled else 0
        self._write(self.ESC + b'E' + bytes([n]))

    def print_text(self, text):
        # ESC/POS usually expects CP437 or similar, but many support UTF-8 or need transliteration.
        # For simplicity, we'll encode to utf-8, but might need cp437 or iconv if printer prints garbage.
        # Many generic printers handle utf-8 if configured, or just ascii.
        # Let's try utf-8 first, fallback to ascii replace.
        try:
            data = text.encode('utf-8')
        except UnicodeEncodeError:
            data = text.encode('ascii', 'replace')
        self._write(data)

    def print_line(self, text=""):
        self.print_text(text + "\n")

    def feed(self, lines=1):
        self._write(self.ESC + b'd' + bytes([lines]))

    def cut(self):
        # GS V m \x00
        # m=65 (feed and cut) usually works
        self._write(self.GS + b'V' + b'\x41' + b'\x00')

    def print_ticket(self, business_info, items, totals):
        """
        business_info: dict with 'name', 'address', 'phone', 'cashier', 'date'
        items: list of dicts with 'name', 'qty', 'price', 'total'
        totals: dict with 'total', 'paid', 'change'
        """
        self.init_printer()

        # Header
        self.set_align('center')
        self.set_bold(True)
        self.print_line(business_info.get('name', 'My Business'))
        self.set_bold(False)
        self.print_line(business_info.get('address', ''))
        self.print_line(business_info.get('phone', ''))
        self.print_line(f"Cashier: {business_info.get('cashier', '')}")
        self.print_line(business_info.get('date', ''))
        self.print_line("-" * 32) # 32 chars is standard for 58mm, 48 for 80mm. Let's assume 32-40 safe width.

        # Items
        self.set_align('left')
        self.print_line(f"{'Product':<20} {'Price':>10}")
        self.print_line("-" * 32)
        
        for item in items:
            name = item['name'][:20] # Truncate name
            qty = item['qty']
            price = item['price'] * qty
            # print line with name
            self.print_line(f"{name}")
            # print qty x price
            self.print_line(f"  {qty} x ${item['price']:.2f} = ${price:.2f}")

        self.print_line("-" * 32)

        # Totals
        self.set_align('right')
        self.set_bold(True)
        self.print_line(f"Total: ${totals['total']:.2f}")
        self.print_line(f"Paid: ${totals['paid']:.2f}")
        self.print_line(f"Change: ${totals['change']:.2f}")
        self.set_bold(False)

        # Footer
        self.set_align('center')
        self.feed(1)
        self.print_line("Thank you for your purchase")
        self.feed(3)
        self.cut()

    def print_report(self, business_info, start_date, end_date, sales_data, cash_flow_data, totals):
        """
        Print sales report.
        sales_data: list of dicts {'time', 'name', 'qty', 'total'}
        cash_flow_data: list of dicts {'time', 'type', 'amount', 'concept'}
        totals: dict {'sales', 'entries', 'exits', 'net'}
        """
        self.init_printer()
        
        # Header
        self.set_align('center')
        self.set_bold(True)
        self.print_line("SALES REPORT")
        self.set_bold(False)
        self.print_line(f"{start_date} - {end_date}")
        self.print_line(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self.print_line("-" * 32)
        
        # Sales
        self.set_align('center')
        self.set_bold(True)
        self.print_line("SALES")
        self.set_bold(False)
        self.set_align('left')
        
        if not sales_data:
             self.set_align('center')
             self.print_line("No sales")
             self.set_align('left')
        else:
            for item in sales_data:
                # item: {'time', 'name', 'qty', 'total'}
                self.print_line(f"{item['name']} (x{item['qty']})")
                # Indent time and total
                self.print_line(f"  {item['time']}   {item['total']}")
        
        self.print_line("-" * 32)
        
        # Cash Flow
        self.set_align('center')
        self.set_bold(True)
        self.print_line("CASH FLOW")
        self.set_bold(False)
        self.set_align('left')

        if not cash_flow_data:
             self.set_align('center')
             self.print_line("No movements")
             self.set_align('left')
        else:
            for item in cash_flow_data:
                # item: {'time', 'type', 'amount', 'concept'}
                symbol = "+" if item['type'] == "entries" else "-" # Note: matching English "entries" from pos_gui if changed there
                self.print_line(f"{symbol} {item['concept']}")
                self.print_line(f"  {item['time']}   {item['amount']}")

        self.print_line("-" * 32)

        # Totals
        self.set_align('right')
        self.set_bold(True)
        self.print_line(f"Total Sales: {totals['sales']}")
        self.print_line(f"Total Entries: {totals['entries']}")
        self.print_line(f"Total Exits: {totals['exits']}")
        self.print_line(f"NET TOTAL: {totals['net']}")
        self.set_bold(False)
        
        # Footer
        self.set_align('center')
        self.feed(1)
        self.print_line("Thank you for using Xun-POS")
        self.feed(3)
        self.cut()
