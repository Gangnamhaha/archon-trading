"""
Design Token System for Stock Platform
======================================
A beginner-friendly, light theme design system for Korean investors.
Inspired by Robinhood and Toss - clean, modern, and trustworthy.

NOT a dark Bloomberg terminal - bright, approachable, high contrast.
"""

DESIGN_TOKENS = {
    # ============================================
    # COLORS - Light, bright, beginner-friendly
    # ============================================
    "colors": {
        # Backgrounds - Clean whites and soft grays
        "bg": "#FFFFFF",              # Main background - pure white
        "bg-secondary": "#F8FAFC",    # Secondary background - very light gray
        "surface": "#FFFFFF",         # Card/panel surfaces
        "surface-hover": "#F1F5F9",   # Hover state for surfaces
        
        # Borders - Subtle, not harsh
        "border": "#E2E8F0",          # Default border
        "border-light": "#F1F5F9",    # Lighter border for subtle separation
        "border-focus": "#3B82F6",    # Focus ring color
        
        # Text - High contrast for readability
        "text": "#0F172A",            # Primary text - near black, high contrast
        "text-secondary": "#475569",  # Secondary text - readable gray
        "muted": "#94A3B8",           # Muted/disabled text
        "text-inverse": "#FFFFFF",   # Text on dark backgrounds
        
        # Primary - Trustworthy blue (not too bright, not corporate navy)
        "primary": "#3B82F6",         # Main brand color - friendly blue
        "primary-hover": "#2563EB",   # Hover state
        "primary-light": "#DBEAFE",   # Light background for primary elements
        "primary-dark": "#1D4ED8",    # Darker variant for emphasis
        
        # Semantic colors - Korean market convention
        "success": "#10B981",         # Profit/gain - vibrant green
        "success-light": "#D1FAE5",   # Light green background
        "success-dark": "#059669",    # Darker green for emphasis
        
        "danger": "#EF4444",          # Loss/drop - clear red
        "danger-light": "#FEE2E2",    # Light red background
        "danger-dark": "#DC2626",     # Darker red for emphasis
        
        "warning": "#F59E0B",         # Warning - attention-grabbing amber
        "warning-light": "#FEF3C7",   # Light amber background
        "warning-dark": "#D97706",    # Darker amber for emphasis
        
        # Additional utility colors
        "info": "#06B6D4",            # Info - cyan
        "info-light": "#CFFAFE",      # Light cyan background
        
        # Chart/visualization colors
        "chart-up": "#10B981",        # Up trend
        "chart-down": "#EF4444",      # Down trend
        "chart-neutral": "#64748B",   # Neutral/flat
    },
    
    # ============================================
    # TYPOGRAPHY - Pretendard for Korean
    # ============================================
    "typography": {
        "fontFamily": "'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans KR', sans-serif",
        "fontFamilyMono": "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        
        # Font sizes - Clear hierarchy
        "fontSize": {
            "h1": "2.25rem",    # 36px - Page titles
            "h2": "1.75rem",    # 28px - Section titles
            "h3": "1.25rem",    # 20px - Subsection titles
            "h4": "1.125rem",   # 18px - Card titles
            "body": "1rem",     # 16px - Body text
            "body-sm": "0.875rem",  # 14px - Small body text
            "caption": "0.75rem",   # 12px - Captions, labels
            "overline": "0.625rem", # 10px - Overlines, tags
        },
        
        # Font weights
        "fontWeight": {
            "regular": "400",
            "medium": "500",
            "semibold": "600",
            "bold": "700",
        },
        
        # Line heights
        "lineHeight": {
            "tight": "1.25",    # Headings
            "normal": "1.5",    # Body text
            "relaxed": "1.75",  # Long-form content
        },
        
        # Letter spacing
        "letterSpacing": {
            "tight": "-0.025em",
            "normal": "0",
            "wide": "0.025em",
            "wider": "0.05em",  # For overlines/caps
        },
    },
    
    # ============================================
    # SPACING - 8px grid system
    # ============================================
    "spacing": {
        "0": "0",
        "xs": "0.25rem",    # 4px
        "sm": "0.5rem",     # 8px
        "md": "1rem",       # 16px
        "lg": "1.5rem",     # 24px
        "xl": "2rem",       # 32px
        "2xl": "2.5rem",    # 40px
        "3xl": "3rem",      # 48px
        "4xl": "4rem",      # 64px
    },
    
    # ============================================
    # BORDER RADIUS - Soft, modern corners
    # ============================================
    "radius": {
        "none": "0",
        "sm": "0.25rem",    # 4px - Buttons, small elements
        "md": "0.5rem",     # 8px - Cards, inputs
        "lg": "0.75rem",    # 12px - Larger cards
        "xl": "1rem",       # 16px - Modals, large cards
        "2xl": "1.5rem",    # 24px - Feature cards
        "full": "9999px",   # Pills, avatars
    },
    
    # ============================================
    # SHADOWS - Subtle depth, not harsh
    # ============================================
    "shadows": {
        "none": "none",
        "sm": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",  # Subtle lift
        "md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",  # Cards
        "lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",  # Dropdowns
        "xl": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",  # Modals
        "inner": "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",  # Inset for inputs
    },
    
    # ============================================
    # MOBILE - Touch-friendly targets
    # ============================================
    "mobile": {
        "minTouchTarget": "48px",       # Minimum touch target size (WCAG)
        "bottomNavHeight": "64px",      # Bottom navigation bar height
        "topBarHeight": "56px",         # Top app bar height
        "safeAreaTop": "env(safe-area-inset-top)",
        "safeAreaBottom": "env(safe-area-inset-bottom)",
        "horizontalPadding": "16px",    # Side padding for mobile
        "cardPadding": "16px",          # Card internal padding
    },
    
    # ============================================
    # TRANSITIONS - Smooth, not jarring
    # ============================================
    "transitions": {
        "fast": "150ms ease",
        "normal": "200ms ease",
        "slow": "300ms ease",
        "bounce": "300ms cubic-bezier(0.68, -0.55, 0.265, 1.55)",
    },
    
    # ============================================
    # Z-INDEX - Layering system
    # ============================================
    "zIndex": {
        "base": "0",
        "dropdown": "100",
        "sticky": "200",
        "modal": "300",
        "popover": "400",
        "tooltip": "500",
        "toast": "600",
        "overlay": "700",
    },
    
    # ============================================
    # BREAKPOINTS - Responsive design
    # ============================================
    "breakpoints": {
        "sm": "640px",
        "md": "768px",
        "lg": "1024px",
        "xl": "1280px",
        "2xl": "1536px",
    },
}


def generate_css() -> str:
    """
    Generate CSS custom properties from DESIGN_TOKENS.
    
    Returns:
        str: A <style> tag containing CSS custom properties.
    
    Example:
        >>> css = generate_css()
        >>> st.markdown(css, unsafe_allow_html=True)
    """
    css_lines = [
        "<style>",
        ":root {",
    ]
    
    # Colors
    colors = DESIGN_TOKENS["colors"]
    for name, value in colors.items():
        # Convert camelCase to kebab-case for CSS
        css_name = _to_kebab_case(name)
        css_lines.append(f"  --color-{css_name}: {value};")
    
    # Typography
    typo = DESIGN_TOKENS["typography"]
    css_lines.append(f"  --font-family: {typo['fontFamily']};")
    css_lines.append(f"  --font-family-mono: {typo['fontFamilyMono']};")
    
    for name, value in typo["fontSize"].items():
        css_name = _to_kebab_case(name)
        css_lines.append(f"  --font-size-{css_name}: {value};")
    
    for name, value in typo["fontWeight"].items():
        css_lines.append(f"  --font-weight-{name}: {value};")
    
    for name, value in typo["lineHeight"].items():
        css_lines.append(f"  --line-height-{name}: {value};")
    
    for name, value in typo["letterSpacing"].items():
        css_name = _to_kebab_case(name)
        css_lines.append(f"  --letter-spacing-{css_name}: {value};")
    
    # Spacing
    spacing = DESIGN_TOKENS["spacing"]
    for name, value in spacing.items():
        css_lines.append(f"  --spacing-{name}: {value};")
    
    # Radius
    radius = DESIGN_TOKENS["radius"]
    for name, value in radius.items():
        css_lines.append(f"  --radius-{name}: {value};")
    
    # Shadows
    shadows = DESIGN_TOKENS["shadows"]
    for name, value in shadows.items():
        css_name = _to_kebab_case(name)
        css_lines.append(f"  --shadow-{css_name}: {value};")
    
    # Mobile
    mobile = DESIGN_TOKENS["mobile"]
    for name, value in mobile.items():
        css_name = _to_kebab_case(name)
        css_lines.append(f"  --mobile-{css_name}: {value};")
    
    # Transitions
    transitions = DESIGN_TOKENS["transitions"]
    for name, value in transitions.items():
        css_lines.append(f"  --transition-{name}: {value};")
    
    # Z-Index
    z_index = DESIGN_TOKENS["zIndex"]
    for name, value in z_index.items():
        css_lines.append(f"  --z-index-{name}: {value};")
    
    # Breakpoints
    breakpoints = DESIGN_TOKENS["breakpoints"]
    for name, value in breakpoints.items():
        css_lines.append(f"  --breakpoint-{name}: {value};")
    
    css_lines.append("}")
    
    # Add utility classes for common patterns
    css_lines.extend(_generate_utility_classes())
    
    css_lines.append("</style>")
    
    return "\n".join(css_lines)


def _to_kebab_case(name: str) -> str:
    """Convert camelCase or PascalCase to kebab-case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("-")
        result.append(char.lower())
    return "".join(result)


def _generate_utility_classes() -> list[str]:
    """Generate utility CSS classes for common patterns."""
    return [
        "",
        "/* Utility Classes */",
        ".text-profit { color: var(--color-success); }",
        ".text-loss { color: var(--color-danger); }",
        ".bg-profit { background-color: var(--color-success-light); }",
        ".bg-loss { background-color: var(--color-danger-light); }",
        "",
        "/* Card base styles */",
        ".card {",
        "  background: var(--color-surface);",
        "  border: 1px solid var(--color-border);",
        "  border-radius: var(--radius-md);",
        "  box-shadow: var(--shadow-sm);",
        "}",
        "",
        "/* Button base styles */",
        ".btn-primary {",
        "  background: var(--color-primary);",
        "  color: var(--color-text-inverse);",
        "  border-radius: var(--radius-sm);",
        "  padding: var(--spacing-sm) var(--spacing-md);",
        "  font-weight: var(--font-weight-medium);",
        "  transition: background var(--transition-fast);",
        "}",
        ".btn-primary:hover {",
        "  background: var(--color-primary-hover);",
        "}",
        "",
        "/* Input base styles */",
        ".input {",
        "  background: var(--color-bg);",
        "  border: 1px solid var(--color-border);",
        "  border-radius: var(--radius-sm);",
        "  padding: var(--spacing-sm) var(--spacing-md);",
        "  font-size: var(--font-size-body);",
        "  color: var(--color-text);",
        "}",
        ".input:focus {",
        "  outline: none;",
        "  border-color: var(--color-border-focus);",
        "  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);",
        "}",
    ]


# Export commonly used tokens for direct access
COLORS = DESIGN_TOKENS["colors"]
TYPOGRAPHY = DESIGN_TOKENS["typography"]
SPACING = DESIGN_TOKENS["spacing"]
RADIUS = DESIGN_TOKENS["radius"]
SHADOWS = DESIGN_TOKENS["shadows"]
MOBILE = DESIGN_TOKENS["mobile"]
TRANSITIONS = DESIGN_TOKENS["transitions"]
Z_INDEX = DESIGN_TOKENS["zIndex"]
BREAKPOINTS = DESIGN_TOKENS["breakpoints"]


if __name__ == "__main__":
    # Print CSS for testing
    print(generate_css())
