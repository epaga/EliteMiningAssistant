# Elite Dangerous Trading Assistant

*"Because alt-tabbing between ED and Inara is so 3307..."*

This is a fun little pair of Python scripts that help you find the best places to mine and sell your hard-earned space minerals in Elite Dangerous. They read your game's journal files to figure out what you're hauling and where you are, then tell you (literally, they speak!) where to mine and where to get the best bang for your void opals.

Created entirely through pair programming with Cursor's AI Agent (including this README), because who needs human co-pilots when you have artificial ones? 🤖

## Features

### Mining Assistant (`ed_mining_finder.py`)
- 🎯 Finds the closest high-density rings for your chosen material
- 💎 Supports all major mining materials (Void Opals, LTDs, Painite, etc.)
- 📍 Uses your current location from the game
- 🗣️ Speaks the system name phonetically (no more squinting at weird star names)
- 📋 Auto-copies system name to clipboard

### Trading Assistant (`ed_cargo_reader.py`)
- 💰 Finds the best selling stations within 100 light years
- 🚫 Filters out small landing pads by default
- 📊 Smart price/distance balancing (won't send you 90ly for an extra 1k credits)
- 📋 Auto-copies station names to clipboard

Both scripts feature:
- 🗣️ Text-to-speech announcements (keep your eyes on those pirates)
- 🎮 VoiceAttack ready! (see Usage section)

## Installation

1. Make sure you have Python 3.10+ installed (I use 3.10.6)
2. Clone this repo:
   ```bash
   git clone https://github.com/yourusername/ed-trading-assistant.git
   cd ed-trading-assistant
   ```
3. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```

## A Note on EDTools Usage

These scripts fetch data from [EDTools](https://edtools.cc/), a fantastic resource for Elite Dangerous miners and traders. A few important points:

- The scripts use the same endpoints as the website's own UI, so they shouldn't cause any extra load
- They include proper delays and rate limiting (just like a human clicking around)
- Each request is for a single material/system (no bulk scraping)
- Results are spoken immediately (no data hoarding)

Basically, we're just automating what you'd do manually on the site. Big thanks to EDTools for providing this service to the community! 🙏

## Usage

### Mining Assistant
```bash
# Find Void Opal hotspots near you
python ed_mining_finder.py "Void Opal"

# Look for other materials
python ed_mining_finder.py "Painite"
python ed_mining_finder.py "Low Temperature Diamond"

# Only show high density rings (default is 7.0)
python ed_mining_finder.py "Void Opal" --min-density 8.5

# Only show rings within 50 light years
python ed_mining_finder.py "Void Opal" --max-distance 50

# Only show icy rings
python ed_mining_finder.py "Void Opal" --ring-type Icy

# Search from a different system
python ed_mining_finder.py "Void Opal" --system "Sol"

# Show all options
python ed_mining_finder.py --help
```

### Trading Assistant
```bash
# Find where to sell your current cargo
python ed_cargo_reader.py

# Check prices for a specific material
python ed_cargo_reader.py --material "Void Opal"

# Check prices closest to a different system
python ed_cargo_reader.py --system "Sol"

# Only show large pad stations
python ed_cargo_reader.py --pad L

# Include small pads in the search
python ed_cargo_reader.py --pad S

# Disable text-to-speech (but why would you?)
python ed_cargo_reader.py --no-voice

# Show all options
python ed_cargo_reader.py --help
```

### VoiceAttack Integration
Want to feel like a proper space captain? Set up these voice commands in VoiceAttack:

1. "Where can I sell this stuff?"
   ```
   python path\to\ed_cargo_reader.py
   ```

2. "Find me some Void Opals nearby"
   ```
   python path\to\ed_mining_finder.py "Void Opal"
   ```

Now you can boss around your computer while you're busy aligning with that mail slot.

## Supported Materials

Both scripts support these materials:
- Void Opals
- Low Temperature Diamonds
- Painite
- Benitoite
- Serendibite
- Monazite
- Musgravite
- Platinum
- Grandidierite

## How It Works

These scripts do some sneaky data fetching from edtools.cc. They:

1. Read your Elite Dangerous journal to find your current system and cargo
2. Get system coordinates from edtools.cc
3. Fetch current mining/market data
4. Use MATH™ to find the best options
5. Tell you where to go (in a nice, polite way)

## Credits

- Created with [Cursor](https://cursor.sh/) - The AI pair programmer that doesn't complain about long supercruise journeys
- Mining & Market data from [EDTools](https://edtools.cc/) - The real MVP
- Voice synthesis by `pyttsx3` - Because reading is hard

## License

MIT License - Feel free to fork, modify, and sell to the Empire (they pay better). 