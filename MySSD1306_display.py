# -*- coding: utf-8 -*-
import time

# after examples from Adafruit SSD1306
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

# display variables
disp = None
width = None
height = None
image = None
draw = None
# Load default font.
font = None
fntSize = 8
# Alternatively load a TTF font.  Make sure the .ttf font file is in the same directory as this python script!
# Some nice fonts to try: http://www.dafont.com/bitmap.php
# font = ImageFont.truetype('Minecraftia.ttf', 8)
Lines = None
stop = False

# initialize the display, return ref to the display
def InitDisplay(type,size):
    global disp, width, height, image, draw

    # Raspberry Pi pin configuration:
    RST = 24
    # Note the following are only used with SPI:
    DC = 23
    SPI_PORT = 0
    SPI_DEVICE = 0
    
    if type == 'I2C' and size == '128x32':
        # 128x32 display with hardware I2C:
        disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)
    elif type == 'I2C' and size == '128x64':
        # 128x64 display with hardware I2C:
        disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)
    elif type == 'SPI' and size == '128x32':
        # 128x32 display with hardware SPI:
        disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))
    elif type == 'SPI' and size == '128x64':
        # 128x64 display with hardware SPI:
        disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))
    else: raise ValueError("Unknown Adafruit Display.")

    # Initialize library.
    disp.begin()
    # Get display width and height.
    width = disp.width
    height = disp.height
    
    # Clear display.
    disp.clear()
    disp.display()

    ClearDisplay()

    return True

def ClearDisplay():
    global image, draw

    # image with mode '1' for 1-bit color
    image = Image.new('1', (width, height))
    
    # Create drawing object
    draw = ImageDraw.Draw(image)
    # draw.rectangle((0,0,width-1,height-1), outline=1, fill=0)

    return True
    

# add a line to the pool
# TO DO: font and font size is per line now
def addLine(text,**args):
    global Lines, font, fntSize, draw
    if ('font' in args.keys()) and (type(args['font']) is str):
        if 'size' in args.keys(): fntSize = int(args['size'])
        try:
            font = ImageFont.truetype(args['font'],fntSize)
        except:
            font = None
    if font == None:
        font = ImageFont.load_default(); fntSize = 8
        
    MaxW, MaxH = draw.textsize(text, font=font)
    if Lines == None: Lines = []
    Lines.append( {
        'x':1,'MaxH': MaxH,
        'txt':text,
        'fnt': font,
        'fill': 255 if not 'fill' in args.keys() else args['fill'],
        'maxW': MaxW,
        'timing': int(time.time()),
        })
    return True

# allow to scroll if text width exceeds display width
def scroll(linenr,yPos):
    global Lines, width, height, draw
    # baseY = yPos+Lines[linenr]['MaxH']
    if yPos > height: return False
    if not 'trimmed' in Lines[linenr].keys(): Lines[linenr]['trimmed'] = False 
    if (not Lines[linenr]['trimmed']) and (Lines[linenr]['maxW'] > width):
        Lines[linenr]['trimmed'] = True
        Lines[linenr]['txt'] += '  '
        Lines[linenr]['maxW'], unused = draw.textsize(Lines[linenr]['txt'], font=Lines[linenr]['fnt'])
    txt = Lines[linenr]['txt']
    if Lines[linenr]['trimmed']:
        twidth = Lines[linenr]['maxW']
        Lines[linenr]['txt'] = Lines[linenr]['txt'][1:] + Lines[linenr]['txt'][0]
        while twidth >= width:
            txt = txt[0:-1]
            twidth, unused = draw.textsize(txt, font=Lines[linenr]['fnt'])
    draw.text((1, yPos), txt, font=Lines[linenr]['fnt'], fill=Lines[linenr]['fill'])
    return Lines[linenr]['trimmed']

# display as much lines as possible
def Display(lock):
    global Lines, draw, image, disp
    if Lines == None or not len(Lines): return (False,False)
    # ClearDisplay()
    # Clear image buffer by drawing a black filled box.
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    Ypos = 0; trimmedX = False; trimmedY = False
    try:
        with lock: nrLines = len(Lines)
    except:
        nrLines = len(Lines)
    for linenr in range(0,nrLines):
        if Ypos > height:
           trimmedY = True
           break
        if scroll(linenr,Ypos): trimmedX = True
        Ypos += Lines[linenr]['MaxH']
    # Draw the image buffer.
    disp.image(image)
    disp.display()
    return (trimmedX, trimmedY)

# run forever this function
def Show(lock, conf):
    global Lines
    count = 0
    if 'lines' in conf.keys() and (type(conf['lines']) is list):
        Lines = conf['lines']
    if Lines == None: Lines = []
    # TO DO: slow down if there are no changes
    if not 'stop' in conf.keys(): conf['stop'] = False
    while not conf['stop']:
        if not len(Lines):
              time.sleep(5)   # first line has a delay of 5 seconds
              count = 0
              continue
        (trimmedx, trimmedy) = Display(lock)
        if trimmedy:          # scroll vertical, allow 3 seconds for top line to read
            if int(time.time()) - Lines[0]['timing'] > 3:
                try:
                    with lock: Lines.pop(0)
                except:
                    if len(Lines): Lines.pop(0)
        time.sleep(0.1)
        

if __name__ == "__main__":
    InitDisplay('SPI','128x64')
    addLine('First short line',  font=font, fill=255)
    addLine('Second short line')
    addLine('Third line')
    addLine('Forth a longer line, more a the previous line.')
    addLine('Fifth short line.')
    addLine('This might be the last line to be displayed.')
    addLine('Seventh line will scroll the display')

    Show(False,{})