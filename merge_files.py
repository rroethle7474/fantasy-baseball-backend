import pandas as pd
import re
import os

# File paths - update these to your actual file locations
jcl_hitters_path = './pitching_files/JCL-Pitchers.csv'
auction_calculator_path = './pitching_files/p-auction.csv'
projections_path = './pitching_files/p-projections-WHIP.csv'
output_path = './pitching_files/merged_pitchers-updated.csv'
    
def create_name_variants(name):
    """Create different variants of a name to improve matching."""
    if not isinstance(name, str):
        return []
    
    name = name.strip()
    # Create variants without periods, Jr., Sr., etc.
    no_suffix = re.sub(r'\s+(Jr\.?|Sr\.?|III|IV|V|II)$', '', name, flags=re.IGNORECASE)
    no_periods = name.replace('.', '')
    no_periods_suffix = no_suffix.replace('.', '')
    
    return [name, no_suffix, no_periods, no_periods_suffix]

def merge_csv_files():
    print('Reading input files...')
    
    # Read CSV files
    jcl_df = pd.read_csv(jcl_hitters_path)
    auction_df = pd.read_csv(auction_calculator_path)
    projections_df = pd.read_csv(projections_path, encoding='latin1')
    
    print(f'JCLHitters rows: {len(jcl_df)}')
    print(f'Auction Calculator rows: {len(auction_df)}')
    print(f'Projections rows: {len(projections_df)}')
    
    # Create mapping dictionaries for auction and projections data
    auction_map = {}
    for _, row in auction_df.iterrows():
        if pd.notna(row['Name']):
            for variant in create_name_variants(row['Name']):
                auction_map[variant] = row
    
    projections_map = {}
    for _, row in projections_df.iterrows():
        if pd.notna(row['Name']):
            for variant in create_name_variants(row['Name']):
                projections_map[variant] = row
    
    print('Merging data...')
    
    # Prepare columns for the merged data
    # Add FG_ prefix to columns from FanGraphs files
    auction_columns = {col: f'FG_{col}' for col in auction_df.columns if col != 'Name'}
    projections_columns = {col: f'FG_{col}' for col in projections_df.columns if col != 'Name'}
    
    # Create empty columns in the merged DataFrame
    for col in auction_columns.values():
        jcl_df[col] = None
    
    for col in projections_columns.values():
        jcl_df[col] = None
    
    # Merge the data
    auction_matches = 0
    projections_matches = 0
    
    for idx, row in jcl_df.iterrows():
        name_variants = create_name_variants(row['Name'])
        
        # Look for matching auction data
        auction_row = None
        for variant in name_variants:
            if variant in auction_map:
                auction_row = auction_map[variant]
                auction_matches += 1
                break
        
        if auction_row is not None:
            # Add auction data
            for orig_col, new_col in auction_columns.items():
                jcl_df.at[idx, new_col] = auction_row[orig_col]
        
        # Look for matching projection data
        projection_row = None
        for variant in name_variants:
            if variant in projections_map:
                projection_row = projections_map[variant]
                projections_matches += 1
                break
        
        if projection_row is not None:
            # Add projection data
            for orig_col, new_col in projections_columns.items():
                jcl_df.at[idx, new_col] = projection_row[orig_col]
    
    print(f'Total JCL records: {len(jcl_df)}')
    print(f'Records matched with auction data: {auction_matches}')
    print(f'Records matched with projection data: {projections_matches}')
    
    # Write the merged DataFrame to a CSV file
    jcl_df.to_csv(output_path, index=False)
    
    print(f'Merged CSV successfully written to {output_path}')

if __name__ == '__main__':
    merge_csv_files()