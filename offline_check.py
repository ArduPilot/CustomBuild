#!/usr/bin/env python
'''
Check a set of terrain files for corruption
'''
import os
#from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import argparse
import time
import gzip
import shutil
import struct
import crc16

from terrain_gen import TERRAIN_GRID_BLOCK_SIZE_Y, east_blocks, IO_BLOCK_SIZE, TERRAIN_GRID_FORMAT_VERSION, GridBlock

# IO block size is 2048
# Actual size is 1821 bytes
# Last 227 bytes is filling
def check_filled(block, lat_int, lon_int, grid_spacing):
    '''check a block for validity'''
    if len(block) != IO_BLOCK_SIZE - 227:
        print("Bad size {0} of {1}".format(len(block), IO_BLOCK_SIZE))
        return False
    (bitmap, lat, lon, crc, version, spacing) = struct.unpack("<QiiHHH", block[:22])
    if(lat == 0 and lon == 0 and crc == 0 and version == 0 and spacing == 0):
        #print("Empty block")
        return True
    if (str(version) != str(TERRAIN_GRID_FORMAT_VERSION)):
        print("Bad version: " + str(version))
        return False
    if abs(lat_int - (lat/1E7)) > 2 or abs(lon_int - (lon/1E7)) > 2:
        print("Bad lat/lon: {0}, {1}".format((lat/1E7), (lon/1E7)))
        return False
    if spacing != 100:
        print("Bad spacing: " + str(spacing))
        return False
    if bitmap != (1<<56)-1:
        print("Bad bitmap")
        return False

    block = block[:16] + struct.pack("<H", 0) + block[18:]
    crc2 = crc16.crc16xmodem(block[:1821])
    if crc2 != crc:
        print("Bad CRC")
        return False

    # all is good, return lon/lat of block
    return (lat, lon)

if __name__ == '__main__':
    # Create the parser
    parser = argparse.ArgumentParser(description='ArduPilot Terrain DAT file generator')

    # Add the arguments
    # Folder to store processed DAT files
    parser.add_argument('-folder', action="store", dest="folder", default="processedTerrain")
    
    args = parser.parse_args()

    targetFolder = os.path.join(os.getcwd(), args.folder)

    grid_spacing = 100
    

    #for each file in folder
    for file in os.listdir(targetFolder):
        if file.endswith("DAT.gz") or file.endswith("DAT"):
            # It's a compressed tile
            # 1. Check it's a valid gzip
            #print(file)
            tile = None
            try:
                lat_int = int(os.path.basename(file)[1:3])
                if os.path.basename(file)[0:1] == "S":
                    lat_int = -lat_int
                lon_int = int(os.path.basename(file)[4:7])
                if os.path.basename(file)[3:4] == "W":
                    lon_int = -lon_int
                if file.endswith("DAT.gz"):
                    with gzip.open(os.path.join(targetFolder, file), 'rb') as f:
                        tile = f.read()
                else:
                    with open(os.path.join(targetFolder, file), 'rb') as f:
                        tile = f.read()
            except Exception as e:
                print("Bad file: " + file)
                print(e)
            # 2. Is it a valid dat file?
            if (tile):
                
                # 2a. Are the correct number (integer) of blocks present?
                # It will be a multiple of 2048 bytes (block size)
                # There is an missing 227 bytes at the end on the file (2048-1821 = 227), as the 
                # terrain blocks only take up 1821 bytes.
                # APM actually adds the padding on the end, so extra 227 is not needed sometimes
                total_blocks = 0
                if (len(tile)+227) % IO_BLOCK_SIZE == 0:
                    total_blocks = int((len(tile)+227) / IO_BLOCK_SIZE)
                elif len(tile) % IO_BLOCK_SIZE == 0:
                    total_blocks = int(len(tile) / IO_BLOCK_SIZE)
                else:
                    print("Bad file size: {0}. {1} extra bytes at end".format(file, len(tile), len(tile) % IO_BLOCK_SIZE))
                if total_blocks > 4000 or total_blocks < 1000:
                    print(file)
                    print("Error: Has {0} blocks".format(total_blocks))
                # 2b. Does each block have the correct CRC and fields?
                if total_blocks != 0:
                    lat_min = 90 * 1.0e7
                    lat_max = -90 * 1.0e7
                    lon_min = 180 * 1.0e7
                    lon_max = -180 * 1.0e7
                    for blocknum in range(total_blocks):
                        block = tile[(blocknum * IO_BLOCK_SIZE):((blocknum + 1)* IO_BLOCK_SIZE)-227]
                        ret = check_filled(block, lat_int, lon_int, 100)
                        if not ret:
                            print(file)
                            print("Bad data in block {0} of {1}".format(blocknum, total_blocks))
                        else:
                            (lat, lon) = ret
                            lat_min = min(lat_min, lat)
                            lat_max = max(lat_max, lat)
                            lon_min = min(lon_min, lon)
                            lon_max = max(lon_max, lon)
                    lat_min *= 1.0e-7
                    lat_max *= 1.0e-7
                    lon_min *= 1.0e-7
                    lon_max *= 1.0e-7
                    if abs(lat_max-lat_min) < 0.99 or abs(lon_max-lon_min) < 1.00 or abs(lat_max-lat_min) > 1.01 or abs(lon_max-lon_min) > 1.07:
                        print(file)
                        print("Bad tile")                                
                        print("Tile covers ({0},{1}) to ({2},{3})".format(lat_min, lon_min, lat_max, lon_max))
                        print("Tile size is ({0:.4f}, {1:.4f}) degrees".format(lat_max-lat_min, lon_max-lon_min))
            else:
                print("Bad tile: " + file)
    print("Done!")
