import json
from pathlib import Path
from typing import Optional, Dict, List
import os
import requests
from bs4 import BeautifulSoup
import time
import re
import pyttsx3
import sys
import pyperclip
import argparse

class EDMiningFinder:
    def __init__(self, journal_path: Optional[Path] = None, voice_enabled: bool = True):
        self.journal_path = journal_path or Path(r"C:\Users\John\Saved Games\Frontier Developments\Elite Dangerous")
        self.current_system = None
        self.current_system_info = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://edtools.cc/'
        }
        self.engine = pyttsx3.init() if voice_enabled else None

    def get_current_system_info(self) -> Optional[Dict]:
        """Read the latest journal file to find current system information..."""
        if not self.journal_path.exists():
            raise FileNotFoundError(f"Journal directory not found at {self.journal_path}")
        
        # Get the latest journal file
        journal_files = list(self.journal_path.glob("Journal.*.log"))
        if not journal_files:
            raise FileNotFoundError("No journal files found")
        
        latest_journal = max(journal_files, key=lambda x: x.stat().st_mtime)
        
        # Read the journal file from the end to find the last FSDJump or Location event
        with open(latest_journal, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in reversed(lines):
            try:
                event = json.loads(line)
                if event['event'] in ['FSDJump', 'Location']:
                    self.current_system = event['StarSystem']
                    self.current_system_info = {
                        'system_name': event['StarSystem'],
                        'coords': event.get('StarPos'),
                        'body': event.get('Body'),
                        'body_type': event.get('BodyType'),
                        'timestamp': event.get('timestamp'),
                        'population': event.get('Population'),
                        'security': event.get('Security'),
                        'economy': event.get('SystemEconomy'),
                        'government': event.get('SystemGovernment'),
                        'allegiance': event.get('SystemAllegiance')
                    }
                    return self.current_system_info
            except (json.JSONDecodeError, KeyError):
                continue
        
        return None

    def normalize_material(self, material: str) -> str:
        """Convert material names to the format expected by edtools.cc"""
        # Common variations that need to be normalized
        mapping = {
            'Void Opal': 'Opal',
            'Void Opals': 'Opal',
            'Low Temperature Diamond': 'LowTemperatureDiamond',
            'Low Temperature Diamonds': 'LowTemperatureDiamond',
            'LTDs': 'LowTemperatureDiamond',
            'LTD': 'LowTemperatureDiamond'
        }
        return mapping.get(material, material)

    def get_hotspots(self, material: str = "Opal") -> List[Dict]:
        """
        Get hotspot data from edtools.cc for the current system
        
        Args:
            material: The material to search for (e.g., "Opal", "Platinum", etc.)
            
        Returns:
            List of dictionaries containing hotspot information
        """
        if not self.current_system:
            raise ValueError("Current system not found. Please ensure you're in a system.")

        # Normalize material name
        material = self.normalize_material(material)
        url = f"https://edtools.cc/hotspot?s={self.current_system}&m={material}"
        
        try:
            # Single request is enough, the data is returned directly
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the results table - it has id="sys_tbl"
            table = soup.find('table', {'id': 'sys_tbl'})
            if not table:
                return []
                
            hotspots = []
            rows = table.find_all('tr')[1:]  # Skip header row
            if not rows:
                return []
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 7:  # We expect 7 columns
                    try:
                        # Get system name (removing the copy button)
                        system_cell = cols[1].find('span')
                        if system_cell:
                            # Look for the actual system name in the data-clipboard-text attribute
                            copy_button = system_cell.find('a', {'class': 'btn'})
                            if copy_button:
                                system_name = copy_button.get('data-clipboard-text', '').strip()
                            else:
                                system_name = system_cell.text.strip().split()[-1]
                        else:
                            system_name = cols[1].text.strip()
                        
                        # Get ring info and parse hotspots from tooltip
                        ring_cell = cols[2].find('span', {'class': 'hvr'})
                        
                        # Split ring name from hotspots
                        try:
                            # Find the first occurrence of a material (they all end in 'ite' or 'ond')
                            ring_text = ring_cell.text if ring_cell else cols[2].text.strip()
                            matches = re.search(r'(.+?)([A-Z][a-z]+(?:ite|ond).*)', ring_text)
                            if matches:
                                ring_name = matches.group(1).strip()
                                hotspots_text = matches.group(2)
                            else:
                                ring_name = ring_text
                                hotspots_text = ""
                        except Exception:
                            ring_name = ring_cell.text if ring_cell else cols[2].text.strip()
                            hotspots_text = ""
                        
                        tooltip = ring_cell.find('span', {'class': 'ttip'}) if ring_cell else None
                        hotspot_details = []
                        if tooltip:
                            # Each line in tooltip is a "Material:Count" pair
                            hotspot_details = [line.strip() for line in tooltip.text.strip().split('\n')]
                        
                        # Parse ring density and its details from the tooltip
                        density_cell = cols[6].find('span', {'class': 'hvr'})
                        density_text = density_cell.text.strip().split('M=')[0] if density_cell else '0'
                        
                        density_tooltip = density_cell.find('span', {'class': 'ttip'}) if density_cell else None
                        density_details = {}
                        if density_tooltip:
                            # Split by <br/> tags first, then process each part
                            details = [d.strip() for d in density_tooltip.text.split('Inner=')]
                            if len(details) >= 1 and details[0].startswith('M='):
                                try:
                                    density_details['M'] = float(details[0][2:].replace(',', ''))
                                except ValueError:
                                    pass
                            
                            if len(details) >= 2:
                                try:
                                    inner_outer = details[1].split('Outer=')
                                    density_details['Inner'] = float(inner_outer[0].replace(',', ''))
                                    density_details['Outer'] = float(inner_outer[1].replace(',', ''))
                                except (ValueError, IndexError):
                                    pass
                        
                        hotspot = {
                            'system': system_name,
                            'distance': float(cols[0].text.strip()),
                            'ring_name': ring_name,
                            'ring_type': cols[3].text.strip(),
                            'hotspot_count': int(cols[4].text.strip()),
                            'distance_to_arrival': int(cols[5].text.strip().replace(',', '')),
                            'ring_density': float(density_text),
                            'ring_details': density_details,
                            'hotspots': hotspot_details
                        }
                        
                        # Check if system is populated (has a * mark)
                        populated_mark = cols[1].find('span', {'class': 'gr'})
                        hotspot['populated'] = bool(populated_mark)
                        
                        hotspots.append(hotspot)
                    except (ValueError, IndexError, AttributeError) as e:
                        print(f"Error parsing row: {e}")
                        continue
            
            return hotspots
            
        except requests.RequestException as e:
            print(f"Error fetching hotspot data: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text[:500]}...")  # Print first 500 chars of response
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []

    def speak(self, text: str):
        """Speak the given text using text-to-speech"""
        if self.engine:
            self.engine.say(text)
            self.engine.runAndWait()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Elite Dangerous Mining Assistant - Find the best places to mine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('material', nargs='?', default='Void Opal',
                       help='Material to find hotspots for')
    parser.add_argument('--system', '-s', help='System to search from (default: reads from journal)')
    parser.add_argument('--journal-path', '-j', help='Path to Elite Dangerous journal folder')
    parser.add_argument('--no-voice', '-q', action='store_true', help='Disable voice output')
    parser.add_argument('--min-density', '-d', type=float, default=7.0,
                       help='Minimum ring density to consider')
    parser.add_argument('--max-distance', '-m', type=float, default=100.0,
                       help='Maximum distance to search in light years')
    parser.add_argument('--ring-type', '-r', choices=['Icy', 'Rocky', 'Metal', 'Metal Rich', 'Any'],
                       default='Any', help='Type of ring to search for')
    return parser.parse_args()

def main():
    args = parse_args()
    finder = EDMiningFinder(
        journal_path=args.journal_path,
        voice_enabled=not args.no_voice
    )
    
    try:
        # Get current system if not specified
        current_system = args.system
        if not current_system:
            system_info = finder.get_current_system_info()
            if not system_info:
                print("Error: Could not determine current system. Please specify with --system")
                return
            current_system = system_info['system_name']
            
        # Get hotspots and filter by criteria
        material = args.material
        hotspots = finder.get_hotspots(material)
        
        if hotspots:
            # Filter by ring type if specified
            if args.ring_type != 'Any':
                hotspots = [spot for spot in hotspots 
                           if spot['ring_type'].lower() == args.ring_type.lower()]
            
            # Filter by minimum density
            hotspots = [spot for spot in hotspots 
                       if spot['ring_density'] >= args.min_density]
            
            # Filter by maximum distance
            hotspots = [spot for spot in hotspots 
                       if spot['distance'] <= args.max_distance]
            
            if hotspots:
                # Get closest spot
                spot = min(hotspots, key=lambda x: x['distance'])
                
                # Format system name for reading (only if voice enabled)
                system_name = ' '.join(spot['system']) if finder.engine else spot['system']
                
                # Copy system name to clipboard (use original, not spelled out)
                pyperclip.copy(spot['system'])
                
                # Format distance (round to nearest light year)
                distance = round(spot['distance'])
                
                # Format ring name (remove any hotspot text)
                ring_name = spot['ring_name'].strip()
                
                # Add density info
                density_info = f" with {spot['ring_density']:.1f} density"
                
                output = f"{system_name}, {distance} light years away, ring {ring_name}{density_info}"
                print(output)
                print("(System name copied to clipboard)")
                
                if finder.engine:
                    finder.speak(output)
            else:
                msg = f"No suitable hotspots found (min density: {args.min_density}, max distance: {args.max_distance}ly"
                if args.ring_type != 'Any':
                    msg += f", ring type: {args.ring_type}"
                msg += ")"
                print(msg)
                if finder.engine:
                    finder.speak(msg)
        else:
            # Use original material name in error message for clarity
            msg = f"No hotspots found for {args.material}"
            print(msg)
            if finder.engine:
                finder.speak(msg)
                
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 