# 12 maart 2019 Teus
# import MySense
# MySense.runMe()
from machine import Pins
if not Pin('P18',mode=Pin.IN).value():
    import MySense
    MySense.runMe()
