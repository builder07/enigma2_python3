#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigSlider, ConfigYesNo, ConfigNothing
from enigma import eDBoxLCD, eTimer, eActionMap, getBoxType
from Components.SystemInfo import SystemInfo
from Screens.InfoBar import InfoBar
from Screens.Screen import Screen
from Tools.Directories import fileExists
from sys import maxsize
from twisted.internet import threads
import Screens.Standby
import usb
from boxbranding import getMachineBuild
from os import sys

model = getBoxType()
platform = getMachineBuild()

class dummyScreen(Screen):
	skin = """<screen position="0,0" size="0,0" transparent="1">
	<widget source="session.VideoPicture" render="Pig" position="0,0" size="0,0" backgroundColor="transparent" zPosition="1"/>
	</screen>"""
	def __init__(self, session, args=None):
		Screen.__init__(self, session)
		self.close()

def IconCheck(session=None, **kwargs):
	if fileExists("/proc/stb/lcd/symbol_network") or fileExists("/proc/stb/lcd/symbol_usb"):
		global networklinkpoller
		networklinkpoller = IconCheckPoller()
		networklinkpoller.start()

class IconCheckPoller:
	def __init__(self):
		self.timer = eTimer()

	def start(self):
		if self.iconcheck not in self.timer.callback:
			self.timer.callback.append(self.iconcheck)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.iconcheck in self.timer.callback:
			self.timer.callback.remove(self.iconcheck)
		self.timer.stop()

	def iconcheck(self):
		try:
			threads.deferToThread(self.JobTask)
		except:
			pass
		self.timer.startLongTimer(30)

	def JobTask(self):
		LinkState = 0
		if fileExists('/sys/class/net/wlan0/operstate'):
			LinkState = open('/sys/class/net/wlan0/operstate').read()
			if LinkState != 'down':
				LinkState = open('/sys/class/net/wlan0/operstate').read()
		elif fileExists('/sys/class/net/eth0/operstate'):
			LinkState = open('/sys/class/net/eth0/operstate').read()
			if LinkState != 'down':
				LinkState = open('/sys/class/net/eth0/carrier').read()
		LinkState = LinkState[:1]
		if fileExists("/proc/stb/lcd/symbol_network") and config.lcd.mode.value == '1':
			open("/proc/stb/lcd/symbol_network", "w").write(str(LinkState))
		elif fileExists("/proc/stb/lcd/symbol_network") and config.lcd.mode.value == '0':
			open("/proc/stb/lcd/symbol_network", "w").write("0")

		USBState = 0
		busses = usb.busses()
		for bus in busses:
			devices = bus.devices
			for dev in devices:
				if dev.deviceClass != 9 and dev.deviceClass != 2 and dev.idVendor != 3034 and dev.idVendor > 0:
					USBState = 1
		if fileExists("/proc/stb/lcd/symbol_usb"):
			open("/proc/stb/lcd/symbol_usb", "w").write(str(USBState))

		self.timer.startLongTimer(30)

class LCD:
	def __init__(self):
		eActionMap.getInstance().bindAction('', -sys.maxsize -1, self.DimUpEvent)
		self.autoDimDownLCDTimer = eTimer()
		self.autoDimDownLCDTimer.callback.append(self.autoDimDownLCD)
		self.autoDimUpLCDTimer = eTimer()
		self.autoDimUpLCDTimer.callback.append(self.autoDimUpLCD)
		self.currBrightness = self.dimBrightness = self.Brightness = None
		self.dimDelay = 0
		config.misc.standbyCounter.addNotifier(self.standbyCounterChanged, initial_call = False)

	def standbyCounterChanged(self, configElement):
		Screens.Standby.inStandby.onClose.append(self.leaveStandby)
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		eActionMap.getInstance().unbindAction('', self.DimUpEvent)

	def leaveStandby(self):
		eActionMap.getInstance().bindAction('', -sys.maxsize -1, self.DimUpEvent)

	def DimUpEvent(self, key, flag):
		self.autoDimDownLCDTimer.stop()
		if not Screens.Standby.inTryQuitMainloop:
			if self.Brightness is not None and not self.autoDimUpLCDTimer.isActive():
				self.autoDimUpLCDTimer.start(10, True)

	def autoDimDownLCD(self):
		if not Screens.Standby.inTryQuitMainloop:
			if self.dimBrightness is not None and  self.currBrightness > self.dimBrightness:
				self.currBrightness = self.currBrightness - 1
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimDownLCDTimer.start(10, True)

	def autoDimUpLCD(self):
		if not Screens.Standby.inTryQuitMainloop:
			self.autoDimDownLCDTimer.stop()
			if self.currBrightness < self.Brightness:
				self.currBrightness = self.currBrightness + 5
				if self.currBrightness >= self.Brightness:
					self.currBrightness = self.Brightness
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimUpLCDTimer.start(10, True)
			else:
				if self.dimBrightness is not None and self.currBrightness > self.dimBrightness and self.dimDelay is not None and self.dimDelay > 0:
					self.autoDimDownLCDTimer.startLongTimer(self.dimDelay)

	def setBright(self, value):
		value *= 255
		value //= 10
		if value > 255:
			value = 255
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		self.currBrightness = self.Brightness = value
		eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
		if self.dimBrightness is not None and  self.currBrightness > self.dimBrightness:
			if self.dimDelay is not None and self.dimDelay > 0:
				self.autoDimDownLCDTimer.startLongTimer(self.dimDelay)

	def setStandbyBright(self, value):
		value *= 255
		value //= 10
		if value > 255:
			value = 255
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		self.Brightness = value
		if self.dimBrightness is None:
			self.dimBrightness = value
		if self.currBrightness is None:
			self.currBrightness = value
		eDBoxLCD.getInstance().setLCDBrightness(self.Brightness)

	def setDimBright(self, value):
		value *= 255
		value //= 10
		if value > 255:
			value = 255
		self.dimBrightness = value

	def setDimDelay(self, value):
		self.dimDelay = int(value)

	def setContrast(self, value):
		value *= 63
		value //= 20
		if value > 63:
			value = 63
		eDBoxLCD.getInstance().setLCDContrast(value)

	def setInverted(self, value):
		if value:
			value = 255
		eDBoxLCD.getInstance().setInverted(value)

	def setFlipped(self, value):
		eDBoxLCD.getInstance().setFlipped(value)

	def setScreenShot(self, value):
 		eDBoxLCD.getInstance().setDump(value)

	def isOled(self):
		return eDBoxLCD.getInstance().isOled()

	def setMode(self, value):
		if fileExists("/proc/stb/lcd/show_symbols"):
			print('[Lcd] setLCDMode',value)
			open("/proc/stb/lcd/show_symbols", "w").write(value)
		if config.lcd.mode.value == "0":
			SystemInfo["SeekStatePlay"] = False
			SystemInfo["StatePlayPause"] = False
			if fileExists("/proc/stb/lcd/symbol_hdd"):
				open("/proc/stb/lcd/symbol_hdd", "w").write("0")
			if fileExists("/proc/stb/lcd/symbol_hddprogress"):
				open("/proc/stb/lcd/symbol_hddprogress", "w").write("0")
			if fileExists("/proc/stb/lcd/symbol_network"):
				open("/proc/stb/lcd/symbol_network", "w").write("0")
			if fileExists("/proc/stb/lcd/symbol_signal"):
				open("/proc/stb/lcd/symbol_signal", "w").write("0")
			if fileExists("/proc/stb/lcd/symbol_timeshift"):
				open("/proc/stb/lcd/symbol_timeshift", "w").write("0")
			if fileExists("/proc/stb/lcd/symbol_tv"):
				open("/proc/stb/lcd/symbol_tv", "w").write("0")
			if fileExists("/proc/stb/lcd/symbol_usb"):
				open("/proc/stb/lcd/symbol_usb", "w").write("0")

	def setPower(self, value):
		if fileExists("/proc/stb/power/vfd"):
			print('[Lcd] setLCDPower',value)
			open("/proc/stb/power/vfd", "w").write(value)
		elif fileExists("/proc/stb/lcd/vfd"):
			print('[Lcd] setLCDPower',value)
			open("/proc/stb/lcd/vfd", "w").write(value)

	def setShowoutputresolution(self, value):
		if fileExists("/proc/stb/lcd/show_outputresolution"):
			print('[Lcd] setLCDShowoutputresolution',value)
			open("/proc/stb/lcd/show_outputresolution", "w").write(value)

	def setfblcddisplay(self, value):
		if fileExists("/proc/stb/fb/sd_detach"):
			print('[Lcd] setfblcddisplay',value)
			open("/proc/stb/fb/sd_detach", "w").write(value)

	def setRepeat(self, value):
		if fileExists("/proc/stb/lcd/scroll_repeats"):
			print('[Lcd] setLCDRepeat',value)
			open("/proc/stb/lcd/scroll_repeats", "w").write(value)

	def setScrollspeed(self, value):
		if fileExists("/proc/stb/lcd/scroll_delay"):
			print('[Lcd] setLCDScrollspeed',value)
			open("/proc/stb/lcd/scroll_delay", "w").write(value)

	def setLEDNormalState(self, value):
		eDBoxLCD.getInstance().setLED(value, 0)

	def setLEDDeepStandbyState(self, value):
		eDBoxLCD.getInstance().setLED(value, 1)

	def setLEDBlinkingTime(self, value):
		eDBoxLCD.getInstance().setLED(value, 2)

	def setLCDMiniTVMode(self, value):
		if fileExists("/proc/stb/lcd/mode"):
			print('[Lcd] setLCDMiniTVMode',value)
			open("/proc/stb/lcd/mode", "w").write(value)

	def setLCDMiniTVPIPMode(self, value):
		print('[Lcd] setLCDMiniTVPIPMode',value)

	def setLCDMiniTVFPS(self, value):
		if fileExists("/proc/stb/lcd/fps"):
			print('[Lcd] setLCDMiniTVFPS',value)
			open("/proc/stb/lcd/fps", "w").write(value)

def leaveStandby():
	config.lcd.bright.apply()
	if model == "vuultimo":
		config.lcd.ledbrightness.apply()
		config.lcd.ledbrightnessdeepstandby.apply()

def standbyCounterChanged(configElement):
	Screens.Standby.inStandby.onClose.append(leaveStandby)
	config.lcd.standby.apply()
	config.lcd.ledbrightnessstandby.apply()
	config.lcd.ledbrightnessdeepstandby.apply()

def InitLcd():
	detected = eDBoxLCD.getInstance() and eDBoxLCD.getInstance().detected()
	config.lcd = ConfigSubsection();
	if detected:
		def setLCDbright(configElement):
			ilcd.setBright(configElement.value);

		def setLCDcontrast(configElement):
			ilcd.setContrast(configElement.value);

		def setLCDinverted(configElement):
			ilcd.setInverted(configElement.value);

		def setLCDflipped(configElement):
			ilcd.setFlipped(configElement.value);

		standby_default = 0

		ilcd = LCD()

		if not ilcd.isOled():
			config.lcd.contrast = ConfigSlider(default=5, limits=(0, 20))
			config.lcd.contrast.addNotifier(setLCDcontrast);
		else:
			config.lcd.contrast = ConfigNothing()
			standby_default = 1

		config.lcd.standby = ConfigSlider(default=standby_default, limits=(0, 10))
		config.lcd.standby.addNotifier(setLCDbright);
		config.lcd.standby.apply = lambda : setLCDbright(config.lcd.standby)

		config.lcd.bright = ConfigSlider(default=5, limits=(0, 10))
		config.lcd.bright.addNotifier(setLCDbright);
		config.lcd.bright.apply = lambda : setLCDbright(config.lcd.bright)
		config.lcd.bright.callNotifiersOnSaveAndCancel = True

		config.lcd.invert = ConfigYesNo(default=False)
		config.lcd.invert.addNotifier(setLCDinverted);

		config.lcd.flip = ConfigYesNo(default=False)
		config.lcd.flip.addNotifier(setLCDflipped);

		if SystemInfo["LedPowerColor"]:
			def setLedPowerColor(configElement):
				open(SystemInfo["LedPowerColor"], "w").write(configElement.value)
			config.lcd.ledpowercolor = ConfigSelection(default = "1", choices = [("0", _("off")),("1", _("blue")), ("2", _("red")), ("3", _("violet"))])
			config.lcd.ledpowercolor.addNotifier(setLedPowerColor)

		if SystemInfo["LedStandbyColor"]:
			def setLedStandbyColor(configElement):
				open(SystemInfo["LedStandbyColor"], "w").write(configElement.value)
			config.lcd.ledstandbycolor = ConfigSelection(default = "3", choices = [("0", _("off")),("1", _("blue")), ("2", _("red")), ("3", _("violet"))])
			config.lcd.ledstandbycolor.addNotifier(setLedStandbyColor)

		if SystemInfo["LedSuspendColor"]:
			def setLedSuspendColor(configElement):
				open(SystemInfo["LedSuspendColor"], "w").write(configElement.value)
			config.lcd.ledsuspendcolor = ConfigSelection(default = "2", choices = [("0", _("off")),("1", _("blue")), ("2", _("red")), ("3", _("violet"))])
			config.lcd.ledsuspendcolor.addNotifier(setLedSuspendColor)

		if SystemInfo["Power4x7On"]:
			def setPower4x7On(configElement):
				open(SystemInfo["Power4x7On"], "w").write(configElement.value)
			config.lcd.power4x7on = ConfigSelection(default = "on", choices = [("off", _("Off")), ("on", _("On"))])
			config.lcd.power4x7on.addNotifier(setPower4x7On)

		if SystemInfo["Power4x7Standby"]:
			def setPower4x7Standby(configElement):
				open(SystemInfo["Power4x7Standby"], "w").write(configElement.value)
			config.lcd.power4x7standby = ConfigSelection(default = "on", choices = [("off", _("Off")), ("on", _("On"))])
			config.lcd.power4x7standby.addNotifier(setPower4x7Standby)

		if SystemInfo["Power4x7Suspend"]:
			def setPower4x7Suspend(configElement):
				open(SystemInfo["Power4x7Suspend"], "w").write(configElement.value)
			config.lcd.power4x7suspend = ConfigSelection(default = "off", choices = [("off", _("Off")), ("on", _("On"))])
			config.lcd.power4x7suspend.addNotifier(setPower4x7Suspend)

		if SystemInfo["LcdLiveTV"]:
			def lcdLiveTvChanged(configElement):
				setLCDLiveTv(configElement.value)
				configElement.save()
			config.lcd.showTv = ConfigYesNo(default = False)
			config.lcd.showTv.addNotifier(lcdLiveTvChanged)

			if "live_enable" in SystemInfo["LcdLiveTV"]:
				config.misc.standbyCounter.addNotifier(standbyCounterChangedLCDLiveTV, initial_call = False)
	else:
		def doNothing():
			pass
		config.lcd.contrast = ConfigNothing()
		config.lcd.bright = ConfigNothing()
		config.lcd.standby = ConfigNothing()
		config.lcd.bright.apply = lambda : doNothing()
		config.lcd.standby.apply = lambda : doNothing()

	config.misc.standbyCounter.addNotifier(standbyCounterChanged, initial_call = False)

