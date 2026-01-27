
def get_theme_colors(dark_mode=False):
    if dark_mode:
        return {
            "background": "#121212",
            "foreground": "#E0E0E0",
            "secondary_foreground": "#B0B0B0",
            "accent": "#BB86FC",
            "success": "#03DAC6",
            "danger": "#CF6679",
            "surface": "#1E1E1E",
            "on_surface": "#FFFFFF",
            "tree_bg": "#1E1E1E",
            "tree_fg": "#E0E0E0",
            "tree_selected": "#3700B3",
            "field_bg": "#2C2C2C",
            "field_fg": "#FFFFFF",
            "header_bg": "#121212",
            "header_fg": "#FFFFFF",
            "product_field_bg": "#3D3D2D",
            "qty_field_bg": "#2D3D2D",
            "low_stock_bg": "#4D0000",
            "exit_bg": "#000000",
            "exit_fg": "#FFFFFF"
        }
    else:
        return {
            "background": "#F0F0F0",
            "foreground": "#212529",
            "secondary_foreground": "#6C757D",
            "accent": "#007BFF",
            "success": "#28A745",
            "danger": "#DC3545",
            "surface": "#FFFFFF",
            "on_surface": "#1A1A1A",
            "tree_bg": "#FFFFFF",
            "tree_fg": "#212529",
            "tree_selected": "#007BFF",
            "field_bg": "#FFFFFF",
            "field_fg": "#212529",
            "header_bg": "#F0F0F0",
            "header_fg": "#1A1A1A",
            "product_field_bg": "#FFF9C4",
            "qty_field_bg": "#E8F5E9",
            "low_stock_bg": "red",
            "exit_bg": "#000000",
            "exit_fg": "#FFFFFF"
        }
