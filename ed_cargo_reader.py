import json
from pathlib import Path
from typing import Dict, Optional, List
import os
import requests
import pyttsx3
import pyperclip
import math
import argparse

# Material IDs from edtools.cc - these aren't documented anywhere, had to find them by inspecting network requests...so could potentially change
MATERIAL_IDS = {
    'Painite': 83,
    'Low Temperature Diamond': 276,
    'Void Opal': 350,
    'Benitoite': 347,
    'Serendibite': 344,
    'Monazite': 345,
    'Musgravite': 346,
    'Platinum': 46,
    'Grandidierite': 348,
    'grandidierite': 348
}

def round_to_50k(price: int) -> str:
    """Round a price to the nearest 50,000 and return as string with K notation.
    Elite Dangerous prices tend to move in 50k increments, so this makes the numbers more readable."""
    rounded = round(price / 50000) * 50
    return f"{rounded:,} K"

class EDCargoReader:
    def __init__(self, journal_path: Optional[str] = None, voice_enabled: bool = True):
        # Default to standard ED journal location if not specified
        self.journal_path = Path(journal_path or r"C:\Users\John\Saved Games\Frontier Developments\Elite Dangerous")
        
        # Headers to mimic a browser - edtools.cc doesn't like obvious bot requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        # Initialize text-to-speech only if enabled
        self.engine = pyttsx3.init() if voice_enabled else None

    def speak(self, text: str):
        """Speak the given text if voice is enabled"""
        if self.engine:
            self.engine.say(text)
            self.engine.runAndWait()

    def get_main_cargo(self) -> Optional[str]:
        """Read Cargo.json to find the main non-drone cargo material.
        We ignore limpets because they're just mining equipment."""
        cargo_file = self.journal_path / "Cargo.json"
        if not cargo_file.exists():
            raise FileNotFoundError(f"Cargo file not found at {cargo_file}")
        
        with open(cargo_file, 'r', encoding='utf-8') as f:
            try:
                cargo_data = json.load(f)
                
                if 'Inventory' not in cargo_data:
                    return None
                
                # Filter out drones and find highest count item
                non_drone_items = [
                    item for item in cargo_data['Inventory']
                    if item.get('Name', '').lower() != 'drones' 
                    and item.get('Name_Localised', '').lower() != 'limpet'
                ]
                
                if not non_drone_items:
                    return None
                
                # Get the item with highest count
                highest_item = max(non_drone_items, key=lambda x: x.get('Count', 0))
                return highest_item.get('Name_Localised', highest_item.get('Name', 'Unknown'))
                
            except json.JSONDecodeError:
                return None

    def get_commodity_name(self, material_id: int) -> str:
        """Get the correct name to use in trade requests.
        EDTools uses slightly different names than the game for some materials."""
        mapping = {
            83: 'Painite',
            276: 'LowTemperatureDiamond',
            350: 'Opal',
            347: 'Benitoite',
            344: 'Serendibite',
            345: 'Monazite',
            346: 'Musgravite',
            46: 'Platinum',
            348: 'Grandidierite'
        }
        return mapping.get(material_id, '')

    def get_distance(self, sys1_coords: Dict, sys2_coords: Dict) -> float:
        """Calculate distance between two systems using their coordinates.
        Elite uses a simple Euclidean distance in a 3D space."""
        x1, y1, z1 = sys1_coords['x'], sys1_coords['y'], sys1_coords['z']
        x2, y2, z2 = sys2_coords['x'], sys2_coords['y'], sys2_coords['z']
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2) ** 0.5

    def get_best_sell_locations(self, material: str, current_system: str, acceptable_pads: List[str] = None) -> None:
        """Look up best selling locations for the material"""
        # Default to M and L pads if none specified
        if acceptable_pads is None:
            acceptable_pads = ['M', 'L']
            
        material_id = MATERIAL_IDS.get(material)
        if not material_id:
            print(f"Error: No material ID found for {material}")
            return
        
        try:
            # First get system coordinates - needed to calculate real distances
            coords_response = requests.get(
                f"https://edtools.cc/sys_coord.php?s={current_system}", 
                headers=self.headers
            )
            coords_response.raise_for_status()
            coords_data = coords_response.json()
            
            if 'error' in coords_data:
                print(f"Error: {coords_data['error']}")
                return
                
            # Get trading data
            request_name = self.get_commodity_name(material_id)
            trade_response = requests.get(
                f"https://edtools.cc/trd.php?f=json&cmdy={request_name}",
                headers=self.headers
            )
            trade_response.raise_for_status()
            trade_data = trade_response.json()
            
            if not trade_data:
                print("No stations found")
                return
            
            # Calculate distances from reference system
            ref_coords = coords_data['coords']
            valid_stations = []
            
            for station in trade_data:
                if 'coords' in station:
                    # Skip stations with wrong pad size
                    pad = station.get('pad', '').upper()
                    if pad not in acceptable_pads:
                        continue
                        
                    distance = self.get_distance(ref_coords, station['coords'])
                    if distance <= 100:  # Only consider stations within 100 Ly
                        station['distance'] = distance
                        valid_stations.append(station)
            
            if not valid_stations:
                pads_str = '/'.join(acceptable_pads)
                print(f"No suitable stations found within 100 Ly ({pads_str} pads only)")
                return
                
            # Sort by price to find the best price
            by_price = sorted(valid_stations, key=lambda x: x.get('price', 0), reverse=True)
            best_price = by_price[0]['price']
            
            # Find stations that are:
            # 1. Within 100k cr of best price
            # 2. At least 20 Ly closer than the best price station
            # This helps find "good enough" prices that are much closer
            best_price_distance = by_price[0]['distance']
            candidates = []
            
            for station in valid_stations:
                price_diff = best_price - station['price']
                distance_diff = best_price_distance - station['distance']
                
                if price_diff <= 100000 and distance_diff >= 20:
                    candidates.append(station)
                    
            # If we found a closer station with similar price, use it
            # Otherwise use the best price station
            if candidates:
                result = sorted(candidates, key=lambda x: x['distance'])[0]
            else:
                result = by_price[0]
            
            # Copy station name to clipboard for easy copy-paste into game
            pyperclip.copy(result['station'])
            
            # Format and speak the message
            rounded_price = round_to_50k(result['price'])
            message = f"You can sell {material} for about {rounded_price} at {result['station']} in {result['system']}, {result['distance']:.0f} light years away."
            print(message)
            self.speak(message)
            
        except Exception as e:
            print(f"Error fetching data: {e}")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Elite Dangerous Trading Assistant - Find the best places to sell your cargo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--material', '-m', help='Material to check prices for (default: checks your cargo)')
    parser.add_argument('--system', '-s', default='Yoru', help='Current system name')
    parser.add_argument('--journal-path', '-j', help='Path to Elite Dangerous journal folder')
    parser.add_argument('--no-voice', '-q', action='store_true', help='Disable voice output')
    parser.add_argument('--pad', '-p', choices=['S', 'M', 'L', 'ML'], default='ML',
                       help='Required landing pad size (S=Small, M=Medium, L=Large, ML=Medium or Large)')
    return parser.parse_args()

def main():
    args = parse_args()
    reader = EDCargoReader(
        journal_path=args.journal_path,
        voice_enabled=not args.no_voice
    )
    
    try:
        # If no material specified, check cargo
        material = args.material
        if not material:
            material = reader.get_main_cargo()
            if not material:
                material = "Void Opal"
                print(f"No cargo found, searching for {material} prices")
        
        # Convert pad argument to list of acceptable pads
        acceptable_pads = list(args.pad)
        if args.pad == 'ML':
            acceptable_pads = ['M', 'L']
            
        reader.get_best_sell_locations(material, args.system, acceptable_pads)
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 