import os
import random
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

class ChartGenerator:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.primary_color = (13, 27, 42)    # Dark Navy
        self.accent_color = (241, 196, 15)    # Gold
        self.success_color = (46, 204, 113)  # Green
        self.danger_color = (231, 76, 60)    # Red
        self.text_color = (248, 249, 250)    # Off-White

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        # Load a default true-type font. On Windows, Arial is standard.
        # Fall back to default if not found.
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def generate_headline_card(self, headline: str, company: str, sector: str, output_path: str):
        # Create a transparent overlay card (size: 1000x400) to place near the top
        card_w, card_h = 1000, 420
        img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle background (glassmorphism look: semi-transparent navy)
        draw.rounded_rectangle(
            [(10, 10), (card_w - 10, card_h - 10)],
            radius=25,
            fill=(10, 25, 47, 220), # Semi-transparent dark navy
            outline=(241, 196, 15, 255), # Gold outline
            width=3
        )

        # Draw Headline
        font_title = self._get_font(42)
        font_meta = self._get_font(28)
        font_tag = self._get_font(24)

        # Wrap headline text if long
        wrapped_lines = []
        words = headline.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            # Approximate character-width constraint
            if len(test_line) > 36:
                wrapped_lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            wrapped_lines.append(current_line)

        # Draw wrapped lines
        y_offset = 40
        for line in wrapped_lines[:3]: # Limit to 3 lines
            draw.text((50, y_offset), line, font=font_title, fill=self.text_color)
            y_offset += 55

        # Draw Company Tag and Sector Badge
        y_offset = card_h - 100
        if company and company != "N/A":
            # Draw tag box
            draw.rounded_rectangle(
                [(50, y_offset), (400, y_offset + 50)],
                radius=10,
                fill=(46, 204, 113, 200) # Green background
            )
            draw.text((65, y_offset + 10), company[:20], font=font_tag, fill=(255, 255, 255))
            
        if sector and sector != "N/A":
            draw.rounded_rectangle(
                [(450, y_offset), (750, y_offset + 50)],
                radius=10,
                fill=(52, 152, 219, 200) # Blue background
            )
            draw.text((465, y_offset + 10), sector[:18], font=font_tag, fill=(255, 255, 255))

        # Save card
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG")
        print(f"ChartGenerator: Created headline card at {output_path}")

    def generate_stock_chart(self, company_name: str, score: int, output_path: str):
        # Generate a stock line chart using Matplotlib and save it
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=150)
        
        # Mock stock data
        random.seed(score) # Seed to get consistent line shape based on job/score
        prices = [100.0]
        for _ in range(30):
            change = random.uniform(-0.02, 0.035) # Upward bias
            prices.append(prices[-1] * (1 + change))

        # Determine color based on trend
        is_up = prices[-1] >= prices[0]
        color = '#2ecc71' if is_up else '#e74c3c'
        
        # Plot
        ax.plot(prices, color=color, linewidth=4)
        ax.fill_between(range(len(prices)), prices, min(prices)*0.98, color=color, alpha=0.15)
        
        # Custom styles
        fig.patch.set_facecolor('#0a192f')
        ax.set_facecolor('#0a192f')
        ax.spines['bottom'].set_color('#f1c40f')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#f1c40f')
        
        ax.tick_params(colors='#f8f9fa', which='both', labelsize=10)
        ax.grid(True, color='#f1c40f', alpha=0.1, linestyle='--')
        
        ax.set_title(f"{company_name} - Performance", color='#f8f9fa', fontsize=12, fontweight='bold', pad=15)
        
        plt.tight_layout()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        plt.close()
        print(f"ChartGenerator: Created Matplotlib chart at {output_path}")
        
    def generate_percentage_badge(self, movement: float, output_path: str):
        # Create a percentage change badge (e.g. +5.2%)
        card_w, card_h = 320, 160
        img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        is_positive = movement >= 0
        fill_color = self.success_color if is_positive else self.danger_color
        text_val = f"+{movement:.2f}%" if is_positive else f"{movement:.2f}%"
        
        draw.rounded_rectangle(
            [(5, 5), (card_w - 5, card_h - 5)],
            radius=15,
            fill=(*fill_color, 230),
            outline=(255, 255, 255, 255),
            width=2
        )
        
        font_pct = self._get_font(48)
        font_sub = self._get_font(20)
        
        # Text alignment
        draw.text((35, 20), text_val, font=font_pct, fill=(255, 255, 255))
        draw.text((35, 95), "MARKET CHANGE" if is_positive else "MARKET CHANGE", font=font_sub, fill=(255, 255, 255))
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG")
        print(f"ChartGenerator: Created percentage badge at {output_path}")
