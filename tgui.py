'''
	This file is part of Secure Thermostat project.
    Copyright (C) 2017  Sergey Gorbov

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


import wx
from wx.lib.plot import PolyLine, PlotCanvas, PlotGraphics
import wx.lib.scrolledpanel
from wx.lib import buttons, newevent
import os, sys
from PIL import Image
import time
from threading import Thread, Timer, Lock, Event
import config
import tui as UI
import ics_types, ics_proto
import sensor
import atomic
import inspect
from common import *
from  datetime import datetime
from mkpics import *
from pymouse import PyMouse
from collections import OrderedDict
import random

MOUSE = PyMouse()

def blink(gui_control, T_on, T_off):
     gui_control.Show()
     time.sleep(T_on)
     gui_control.Hide(T_off)

def lineno():
    return inspect.currentframe().f_back.f_lineno

def SendEvent(obj, WxEventId):
    cmd = wx.CommandEvent(WxEventId.evtType[0])
    cmd.SetEventObject(obj)
    cmd.SetId(obj.GetId())
    obj.GetEventHandler().ProcessEvent(cmd)

    #~ RIGHT_PANEL_SIZE = (110,MainPanel.SIZE[1]-SIZE[1])
    #~ RIGHT_PANEL_POS = (MainPanel.SIZE[0]-RIGHT_PcANEL_SIZE[0],SIZE[1])
    #~ RIGHT_PANEL_BG = ''

    #~ LEFT_PANEL_SIZE = (110,MainPanel.SIZE[1]-SIZE[1])
    #~ LEFT_PANEL_POS = (0,SIZE[1])
    #~ LEFT_PANEL_BG = ''

class CredMan:
    def __init__(self, username, password, host, port, active_hvac):
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.active_hvac = active_hvac
    @staticmethod
    def cred_save(filename, credentials):
        v = pickle(credentials)
        try:
            f = open(filename, 'w+')
            f.write(v)
            f.close()
        except IOError as err:
            raise UI.UIError("Caching credentials failed: IOError occured", UI.UIError.CREDENTIALS_ERROR)
    @staticmethod
    def cred_load(filename):
        try:
            f = open(filename, 'r')
            v = unpic(f.read())
            f.close()
            if v == None:
                raise UI.UIError("Couldn't retrieve credentials from file {0}".format(filename), UI.UIError.CREDENTIALS_ERROR)
            return v
        except IOError as err:
            print err
            raise UI.UIError("Couldn't open credentials file {0}".format(filename), UI.UIError.CREDENTIALS_ERROR)

REMOTE_API = 'user_interface.CLIENT.'

GLOBAL_ICON_PATH = config.BASE_PATH

ROUND_BUTTON_SIZE = 75, 80

B_SETTINGS_UP = 'B_SETTINGS_UP'
B_SETTINGS_DOWN = 'B_SETTINGS_DOWN'
B_ARROW_UP_UP = 'B_ARROW_UP_UP'
B_ARROW_UP_DOWN = 'B_ARROW_UP_DOWN'
B_ARROW_DOWN_UP = 'B_ARROW_DOWN_UP'
B_ARROW_DOWN_DOWN = 'B_ARROW_DOWN_DOWN'
B_HEAT_UP = 'B_HEAT_UP'
B_HEAT_DOWN = 'B_HEAT_DOWN'
B_COOL_UP = 'B_COOL_UP'
B_COOL_DOWN = 'B_COOL_DOWN'
B_CLIM_UP = 'B_CLIM_UP'
B_CLIM_DOWN = 'B_CLIM_DOWN'
B_FAN_UP = 'B_FAN_UP'
B_FAN_DOWN = 'B_FAN_DOWN'
B_USER_UP = 'B_USER_UP'
B_USER_DOWN = 'B_USER_DOWN'
B_INFO_UP = 'B_INFO_UP'
B_INFO_DOWN = 'B_INFO_DOWN'
B_TIME_UP_UP = 'B_TIME_UP_UP'
B_TIME_UP_DOWN = 'B_TIME_UP_DOWN'
B_TIME_DOWN_UP = 'B_TIME_DOWN_UP'
B_TIME_DOWN_DOWN = 'B_TIME_DOWN_DOWN'
B_REPEAT_UP = 'B_REPEAT_UP'
B_REPEAT_DOWN = 'B_REPEAT_DOWN'
B_POST_UP = 'B_POST_UP'
B_POST_DOWN = 'B_POST_DOWN'

B_DICT = {  B_SETTINGS_UP:'cyan_on.png',
        B_SETTINGS_DOWN:'cyan_off.png',
        B_ARROW_UP_UP:'red_on.png',
        B_ARROW_UP_DOWN:'red_off.png',
        B_ARROW_DOWN_UP:'dark_blue_on.png',
        B_ARROW_DOWN_DOWN:'dark_blue_off.png',
        B_HEAT_UP:'orange_on.png',
        B_HEAT_DOWN:'orange_off.png',
        B_COOL_UP:'blue_on.png',
        B_COOL_DOWN:'blue_off.png',
        B_CLIM_UP:'yellow_on.png',
        B_CLIM_DOWN:'yellow_off.png',
        B_FAN_UP:'green_on.png',
        B_FAN_DOWN:'green_off.png',
        B_USER_UP:'violet_on.png',
        B_USER_DOWN:'violet_off.png',
        B_INFO_UP:'purple_on.png',
        B_INFO_DOWN:'purple_off.png',
        B_TIME_UP_UP:'red_on.png',
        B_TIME_UP_DOWN:'red_off.png',
        B_TIME_DOWN_UP:'dark_blue_on.png',
        B_TIME_DOWN_DOWN:'dark_blue_off.png',
        B_REPEAT_UP:'green_alt_on.png',
        B_REPEAT_DOWN:'green_alt_off.png',
        B_POST_UP:'black_on.png',
        B_POST_DOWN:'black_off.png' }

# Sloppy part. Way not the best implementation of notifications. But fuck it. Wx Pythin is evil
def ShowInfo(frame, message, caption='Information'):
    wx.PostEvent(frame, Notifications.INF(m=message, c=caption))
def ShowWarn(frame, message, caption='Warning'):
    wx.PostEvent(frame, Notifications.WRN(m=message, c=caption))
def ShowError(frame, message, caption='Error'):
    wx.PostEvent(frame, Notifications.ERR(m=message, c=caption))

# This class must be part of any panel in order for them to be able shoing messages
class Notifications:
    
    ERR,  EVT_ERR  = newevent.NewEvent()
    WRN,  EVT_WRN  = newevent.NewEvent()
    INF,  EVT_INF  = newevent.NewEvent()
    
    def __init__(self, frame):
        self.frame = frame
        self.frame.Bind(Notifications.EVT_ERR, self._ShowError)
        self.frame.Bind(Notifications.EVT_WRN, self._ShowWarn)
        self.frame.Bind(Notifications.EVT_INF, self._ShowInfo)
    def _ShowInfo(self, event):
        dlg = wx.MessageDialog(self.frame, event.m, event.c, wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()
        
    def _ShowWarn(self, event):
        dlg = wx.MessageDialog(self.frame, event.m, event.c, wx.OK | wx.ICON_WARNING)
        dlg.ShowModal()
        dlg.Destroy()

    def _ShowError(self, event):
        dlg = wx.MessageDialog(self.frame, event.m, event.c, wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()



class ToggleButton:
    
    ON,  EVT_ON  = newevent.NewEvent()
    OFF, EVT_OFF = newevent.NewEvent()
    FUCK_OFF, EVT_FUCK_OFF = newevent.NewEvent()
    
    STATE_ON = 1
    STATE_OFF = 0
    
    def __init__(self, frame,  bitmap_on_rpath, bitmap_off_rpath, size, pos):
        self.frame = frame
        self.bitmap_on = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_on_rpath), wx.BITMAP_TYPE_PNG)
        self.bitmap_off = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_off_rpath), wx.BITMAP_TYPE_PNG)
        self.button = wx.StaticBitmap(self.frame, -1, self.bitmap_off, pos, size)
        self.button.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)
        self.button.Bind(ToggleButton.EVT_FUCK_OFF, self.onFuckOff)
        self.state = ToggleButton.STATE_OFF
        self.conflicting_button_list = []
        
        self.actOnPressed = None, ()
        self.actOnUnpressed = None, ()
        
        self.button.Bind(ToggleButton.EVT_ON , self.onSwitchOn)
        self.button.Bind(ToggleButton.EVT_OFF, self.onSwitchOff)
    def onLeftDown(self, event):
        if self.state == ToggleButton.STATE_OFF:
            self.state = ToggleButton.STATE_ON
            self.button.SetBitmap(self.bitmap_on)
            if self.actOnPressed[0] != None:
                self.actOnPressed[0](*self.actOnPressed[1])
            self.unpressConflictingButtons()
        else:
            self.state = ToggleButton.STATE_OFF
            self.button.SetBitmap(self.bitmap_off)
            if self.actOnUnpressed[0] != None:
                self.actOnUnpressed[0](*self.actOnUnpressed[1])
    def onFuckOff(self, event):
        if self.state == ToggleButton.STATE_OFF:
            self.state = ToggleButton.STATE_ON
            self.button.SetBitmap(self.bitmap_on)
            self.unpressConflictingButtons()
        else:
            self.state = ToggleButton.STATE_OFF
            self.button.SetBitmap(self.bitmap_off)
    def setConflictingButton(self, button, no_action):
        self.conflicting_button_list.append((button, no_action))
    def unpressConflictingButtons(self):
        for i in self.conflicting_button_list:
            i[0].unpress(i[1])
    def press(self, no_action):
        if self.state == ToggleButton.STATE_OFF:
            if no_action:
                wx.PostEvent(self.button, ToggleButton.FUCK_OFF())
            else:
                SendEvent(self.button, wx.EVT_LEFT_DOWN)
    def unpress(self, no_action):
        if self.state == ToggleButton.STATE_ON:
            if no_action:
                wx.PostEvent(self.button, ToggleButton.FUCK_OFF())
            else:
                SendEvent(self.button, wx.EVT_LEFT_DOWN)
    def setActionOnPressed(self, function, *args):
        self.actOnPressed = function, (args)
    def setActionOnUnpressed(self, function, *args):
        self.actOnUnpressed = function, (args)
    def onSwitchOn(self, evt):
        self.button.Show()
    def onSwitchOff(self, evt):
        self.button.Hide()
    def Show(self):
        wx.PostEvent(self.button, ToggleButton.ON())
    def Hide(self):
        wx.PostEvent(self.button, ToggleButton.OFF())

class ClickButton:
    
    ON,  EVT_ON  = newevent.NewEvent()
    OFF, EVT_OFF = newevent.NewEvent()
    
    def __init__(self, frame,  bitmap_on_rpath, bitmap_off_rpath, size, pos):
        self.frame = frame
        self.bitmap_on = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_on_rpath), wx.BITMAP_TYPE_PNG)
        self.bitmap_off = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_off_rpath), wx.BITMAP_TYPE_PNG)
        self.button = wx.StaticBitmap(self.frame, -1, self.bitmap_off, pos, size)
        self.button.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)
        self.button.Bind(wx.EVT_LEFT_UP, self.onLeftUp)
        
        self.actOnDown = None, ()
        self.actOnUp = None, ()
        
        self.button.Bind(ClickButton.EVT_ON , self.onSwitchOn)
        self.button.Bind(ClickButton.EVT_OFF, self.onSwitchOff)
        
        self.ratio = atomic.AtomicUnit(1)
        
        self.state = atomic.AtomicUnit(0)
        self.token = atomic.AtomicUnit(0)
        self.obj_x, self.obj_y = self.button.GetScreenPosition()
    def isCursorWithin(self):
        xs,ys,xe,ye = self.obj_x, self.obj_y, self.obj_x + ROUND_BUTTON_SIZE[0], self.obj_y + ROUND_BUTTON_SIZE[1]
        cur_x,cur_y = MOUSE.position()
        if cur_x >= xs and cur_x <= xe and cur_y >= ys and cur_y <= ye:
            return True
        return False
    def _caller_(self, function , *args):
        self.token.inc()
        sleep = 1.0
        base_sleep = 0.1
        ct = 0
        token = self.token.get()
        self.ratio.set(1)
        while(self.state.get() == 1) and (self.token.get() == token):
            if not self.isCursorWithin():
                SendEvent(self.button, wx.EVT_LEFT_UP)
                break
            function(*args)
            time.sleep(base_sleep + sleep)
            if sleep > 0.1:
                sleep /= 2
            a = self.ratio.get()
            if a < 32:
                self.ratio.set(int(a*2))
            if(self.state.get() == 0):
                break
    def onLeftDown(self, event):
        self.obj_x, self.obj_y = self.button.GetScreenPosition()
        if self.state.get() == 1:
            SendEvent(self.button, wx.EVT_LEFT_UP)
        else:
            self.state.set(1)
            self.button.SetBitmap(self.bitmap_on)
            if self.actOnDown[0] != None:
                Thread(target=self._caller_, args=(self.actOnDown[0], self.actOnDown[1])).start()
            else:
                #~ time.sleep(1)
                #~ SendEvent(self.button, wx.EVT_LEFT_UP)
                pass
    def onLeftUp(self, event):
        #~ self.obj_x, self.obj_y = self.button.GetScreenPosition()
        if self.state.get() != 0:
            self.state.set(0)
            self.button.SetBitmap(self.bitmap_off)
            if self.actOnUp[0] != None:
                self.actOnUp[0](*self.actOnUp[1])
                #~ Thread(target=self.actOnUp[0], args=self.actOnUp[1]).start()
    def setActionOnDown(self, function, *args):
        self.actOnDown = function, (args)
    def setActionOnUp(self, function, *args):
        self.actOnUp = function, (args)
    def onSwitchOn(self, evt):
        self.button.Show()
    def onSwitchOff(self, evt):
        self.button.Hide()
    def Show(self):
        wx.PostEvent(self.button, ClickButton.ON())
    def Hide(self):
        wx.PostEvent(self.button, ClickButton.OFF())
        

class CustomPanel(wx.Panel):
    def __init__(self, parent, id, size, pos,  bg_rpath=None):
        
        self.control_object = None
        
        # create the panel
        wx.Panel.__init__(self, parent, id, pos=pos, size=size)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.parent = parent
        self.image = None
        if not bg_rpath is None:
            self.image = os.path.join(GLOBAL_ICON_PATH, bg_rpath)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.notifications = Notifications(self)
    def setControlObject(self, control_object):
        self.control_object = control_object
    def OnEraseBackground(self, evt):
        """
        Add a picture to the background
        """
        dc = evt.GetDC()
 
        if not dc:
            dc = wx.ClientDC(self)
            rect = self.GetUpdateRegion().GetBox()
            dc.SetClippingRect(rect)
        dc.Clear()
        if self.image != None:
            bmp = wx.Bitmap(self.image)
            dc.DrawBitmap(bmp, 0, 0)

class ScrollPanel(wx.lib.scrolledpanel.ScrolledPanel):
    def __init__(self, parent, id, size, pos,  bg_rpath=None):
        
        self.control_object = None
        
        # create auxilary panel
        panel_aux = wx.Panel(parent, id, pos=pos, size=(size[0], 0), style=wx.SIMPLE_BORDER)
        panel_aux.Hide()
        # create the panel
        wx.lib.scrolledpanel.ScrolledPanel.__init__(self, parent, id, pos=pos, size=size)
        self.SetupScrolling()
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.parent = parent
        self.image = None
        if not bg_rpath is None:
            self.image = os.path.join(GLOBAL_ICON_PATH, bg_rpath)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.notifications = Notifications(self)
    def setControlObject(self, control_object):
        self.control_object = control_object
    def OnEraseBackground(self, evt):
        """
        Add a picture to the background
        """
        dc = evt.GetDC()
 
        if not dc:
            dc = wx.ClientDC(self)
            rect = self.GetUpdateRegion().GetBox()
            dc.SetClippingRect(rect)
        dc.Clear()
        if self.image != None:
            bmp = wx.Bitmap(self.image)
            dc.DrawBitmap(bmp, 0, 0)

class StatusLight:
    
    ON,  EVT_ON  = newevent.NewEvent()
    OFF, EVT_OFF = newevent.NewEvent()
    
    def __init__(self, frame,  bitmap_on_rpath, bitmap_off_rpath, size, pos):
        self.frame = frame
        self.bitmap_on = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_on_rpath), wx.BITMAP_TYPE_PNG)
        self.bitmap_off = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_off_rpath), wx.BITMAP_TYPE_PNG)
        self.element = wx.StaticBitmap(self.frame, -1, self.bitmap_off, pos, size)
        
        self.element.Bind(StatusLight.EVT_ON , self.onSwitchOn)
        self.element.Bind(StatusLight.EVT_OFF, self.onSwitchOff)
    def onSwitchOn(self, evt):
        self.element.SetBitmap(self.bitmap_on)
    def onSwitchOff(self, evt):
        self.element.SetBitmap(self.bitmap_off)
    def SwitchOn(self):
        wx.PostEvent(self.element, StatusLight.ON())
    def SwitchOff(self):
        wx.PostEvent(self.element, StatusLight.OFF())
    def Bind(self, event, action):
        self.element.Bind(event, action)

class StatusIcon:
    
    ON,  EVT_ON  = newevent.NewEvent()
    OFF, EVT_OFF = newevent.NewEvent()
    
    def __init__(self, frame,  bitmap_rpath, size, pos):
        self.frame = frame
        self.bitmap = wx.Bitmap(os.path.join(GLOBAL_ICON_PATH, bitmap_rpath), wx.BITMAP_TYPE_PNG)
        self.element = wx.StaticBitmap(self.frame, -1, self.bitmap, pos, size)
        
        self.element.Bind(StatusIcon.EVT_ON , self.onSwitchOn)
        self.element.Bind(StatusIcon.EVT_OFF, self.onSwitchOff)
    def onSwitchOn(self, evt):
        self.element.Show()
        self.frame.Layout()
    def onSwitchOff(self, evt):
        self.element.Hide()
        self.frame.Layout()
    def Show(self):
        wx.PostEvent(self.element, StatusIcon.ON())
    def Hide(self):
        wx.PostEvent(self.element, StatusIcon.OFF())

class DynamicText:
    
    TEXT_UPDATE, EVT_TEXT_UPDATE = newevent.NewEvent()
    SHOW, EVT_SHOW  = newevent.NewEvent()
    HIDE, EVT_HIDE = newevent.NewEvent()
    
    def __init__(self, frame, pos, text, size, font=wx.DEFAULT, Type=wx.NORMAL, style=wx.NORMAL, color='grey', shadow=0, stroke=0, stroke_color='black'):
        self.frame = frame
        self.pos = pos
        self.size = size
        self.font = font
        self.Type = Type
        self.style = style
        self.color = color
        self.shadow = shadow
        self.stroke = stroke
        self.stroke_color = stroke_color
        
        self.stroke_l = {}
        self.shadow_l = {}
        
        self.render(frame, pos, text, size, font, Type, style, color, shadow, stroke, stroke_color)
    def render(self, frame, pos, text, size, font, Type, style, color, shadow, stroke, stroke_color, debug=False):
                
        if stroke > 0:
            self.stroke_l['r'] = DynamicText(frame, (pos[0]+stroke,pos[1]), text, size, font,Type, style, stroke_color)
            self.stroke_l['rd'] = DynamicText(frame, (pos[0]+stroke,pos[1]+stroke), text, size, font,Type, style, stroke_color)
            self.stroke_l['d'] = DynamicText(frame, (pos[0],pos[1]+stroke), text, size, font,Type, style, stroke_color)
            self.stroke_l['ld'] = DynamicText(frame, (pos[0]-stroke,pos[1]+stroke), text, size, font,Type, style, stroke_color)
            self.stroke_l['l'] = DynamicText(frame, (pos[0]-stroke,pos[1]), text, size, font,Type, style, stroke_color)
            self.stroke_l['lu'] = DynamicText(frame, (pos[0]-stroke,pos[1]-stroke), text, size, font,Type, style, stroke_color)
            self.stroke_l['u'] = DynamicText(frame, (pos[0],pos[1]-stroke), text, size, font,Type, style, stroke_color)
            self.stroke_l['ur'] = DynamicText(frame, (pos[0]+stroke,pos[1]-stroke), text, size, font,Type, style, stroke_color)
        if shadow > 0:
            self.stroke_l['r'] = DynamicText(frame, (pos[0]+shadow,pos[1]), text, size, font,Type, style, stroke_color)
            self.stroke_l['rd'] = DynamicText(frame, (pos[0]+shadow,pos[1]+shadow), text, size, font,Type, style, stroke_color)
            self.stroke_l['d'] = DynamicText(frame, (pos[0],pos[1]+shadow), text, size, font,Type, style, stroke_color)
            self.stroke_l['ld'] = DynamicText(frame, (pos[0]-shadow,pos[1]+shadow), text, size, font,Type, style, stroke_color)
            self.stroke_l['l'] = DynamicText(frame, (pos[0]-shadow,pos[1]), text, size, font,Type, style, stroke_color)
            self.stroke_l['lu'] = DynamicText(frame, (pos[0]-shadow,pos[1]-shadow), text, size, font,Type, style, stroke_color)
            self.stroke_l['u'] = DynamicText(frame, (pos[0],pos[1]-shadow), text, size, font,Type, style, stroke_color)
            self.stroke_l['ur'] = DynamicText(frame, (pos[0]+shadow,pos[1]-shadow), text, size, font,Type, style, stroke_color)
        
        uppFont = wx.Font(self.size, self.font, self.Type, self.style)
        self.label = wx.StaticText(self.frame, -1, text, pos=self.pos)
        self.label.SetFont(uppFont)
        self.label.SetForegroundColour(self.color)
        self.width = len(text)*self.size
        # Setting an event for the label
        self.label.Bind(DynamicText.EVT_TEXT_UPDATE, self.evtSetText)
        self.label.Bind(DynamicText.EVT_SHOW, self.onShow)
        self.label.Bind(DynamicText.EVT_HIDE, self.onHide)
    def getWidth(self):
        return self.width
    def evtSetText(self, event):
        self.label.SetLabel(event.text)
        for k,v in self.stroke_l.iteritems():
            v.label.SetLabel(event.text)
        for k,v in self.shadow_l.iteritems():
            v.label.SetLabel(event.text)
    def setText(self, text):
        self.width = len(text)*self.size
        wx.PostEvent(self.label, DynamicText.TEXT_UPDATE(text=text))
    def Show(self):
        wx.PostEvent(self.label, DynamicText.SHOW())
    def onShow(self, event):
        self.label.Show()
        for k,v in self.stroke_l.iteritems():
            v.label.Show()
        for k,v in self.shadow_l.iteritems():
            v.label.Show()
    def Hide(self):
        wx.PostEvent(self.label, DynamicText.HIDE())
    def onHide(self, event):
        self.label.Hide()
        for k,v in self.stroke_l.iteritems():
            v.label.Hide()
        for k,v in self.shadow_l.iteritems():
            v.label.Hide()

SHARED_VARIABLE_FOR_UPPER_PANEL_Y_SIZE = 50

class MainPanel(CustomPanel):
    # ADjusts the acceleration for temperature counter
    ACCEL_ADJUSTMENT = 50
    
    SIZE = (config.MAIN_X,config.MAIN_Y)
    POS = (0,0)
    BG = config.BG['OUT']
    X_MARGIN = 75
    Y_MARGIN = 20
    
    GAUGE_SIZE = (SIZE[0], 3)
    GAUGE_POS = (0, SHARED_VARIABLE_FOR_UPPER_PANEL_Y_SIZE)
    
    POST_JOB_TAG = 'POST_JOB'
    TIME_JOB_TAG = 'TIME_JOB'
    TIME_FORMAT = '%Y-%m-%d %H:%M'
    
    POST_JOB, EVENT_POST_JOB = newevent.NewEvent()
    
    def __init__(self, frame):
        self.parent = frame
        super(MainPanel, self).__init__(self.parent, -1, size=MainPanel.SIZE, pos=MainPanel.POS, bg_rpath=MainPanel.BG)
        
        # Bind the job posting event to the main panel
        self.Bind(MainPanel.EVENT_POST_JOB, self._post_)
        
        spacing = 20
        xpos = 0
        # Up and Down buttons
        ypos = 45
        self.temp_up_b = ClickButton(self, B_DICT[B_ARROW_UP_DOWN], B_DICT[B_ARROW_UP_UP], ROUND_BUTTON_SIZE, (MainPanel.X_MARGIN + xpos, MainPanel.Y_MARGIN + ypos))
        self.temp_up_b.setActionOnDown(self.onUp)
        xpos = 0
        ypos += ROUND_BUTTON_SIZE[0] + 6*spacing
        self.temp_down_b = ClickButton(self, B_DICT[B_ARROW_DOWN_DOWN], B_DICT[B_ARROW_DOWN_UP], ROUND_BUTTON_SIZE, (MainPanel.X_MARGIN + xpos, MainPanel.Y_MARGIN + ypos))
        self.temp_down_b.setActionOnDown(self.onDown)
        
        # Repeat and Submit buttons
        xpos = (ROUND_BUTTON_SIZE[0] + spacing)*4
        ypos = 240
        self.repeat_b = ToggleButton(self, B_DICT[B_REPEAT_DOWN], B_DICT[B_REPEAT_UP], ROUND_BUTTON_SIZE, (MainPanel.X_MARGIN + xpos, MainPanel.Y_MARGIN + ypos))
        self.repeat_b.setActionOnPressed(self.onRepeat)
        self.repeat_b.setActionOnUnpressed(self.onRepeat)
        xpos += (ROUND_BUTTON_SIZE[0] + spacing)*2
        self.post_b = ClickButton(self, B_DICT[B_POST_DOWN], B_DICT[B_POST_UP], ROUND_BUTTON_SIZE, (MainPanel.X_MARGIN + xpos, MainPanel.Y_MARGIN + ypos))
        self.post_b.setActionOnDown(self._dummy_)
        self.post_b.setActionOnUp(self.onPost)
        
        # Time buttons
        xpos = 380
        xpos += (ROUND_BUTTON_SIZE[0] + spacing)*1
        ypos = 45
        self.time_up_b = ClickButton(self, B_DICT[B_TIME_UP_DOWN], B_DICT[B_TIME_UP_UP], ROUND_BUTTON_SIZE, (MainPanel.X_MARGIN + xpos, MainPanel.Y_MARGIN + ypos))
        self.time_up_b.setActionOnDown(self.timeUp)
        ypos += ROUND_BUTTON_SIZE[0] + 6*spacing
        self.time_down_b = ClickButton(self, B_DICT[B_TIME_DOWN_DOWN], B_DICT[B_TIME_DOWN_UP], ROUND_BUTTON_SIZE, (MainPanel.X_MARGIN + xpos, MainPanel.Y_MARGIN + ypos))
        self.time_down_b.setActionOnDown(self.timeDown)
        
        
        self.t_val = atomic.AtomicUnit(config.TEMP_MIN)
        
        self.t_ctrl = DynamicText(self, (60,160), str(config.TEMP_MIN), 60, style=wx.BOLD, color='white', stroke=2)
        self.t_ind = DynamicText(self, (180,120), str(config.TEMP_MIN), 110, style=wx.BOLD, color='white', stroke=2)
        
        # Time
        self.delay_seconds = 0
        self.itime = 0
        self.strptime = 0
        self.time_val = atomic.AtomicUnit('--:--')
        self.time = DynamicText(self, (520,180), self.time_val.get(), 35, style=wx.BOLD, color='white', stroke=2)
        
        # Mode Label
        self.mode_label = DynamicText(self, (200,300), "OFF", 30, style=wx.BOLD, color='white', stroke=2)
        self.fan_label = DynamicText(self, (200,260), "FAN AUTO", 30, style=wx.BOLD, color='white', stroke=2)
        
        # Job detail
        self.j_detail = DynamicText(self, (MainPanel.X_MARGIN + ROUND_BUTTON_SIZE[0] + spacing, MainPanel.Y_MARGIN + 50), "No job set", 11, style=wx.NORMAL, color='white', stroke=1)
        
        self.parent.SC.enter(self.TimeJob, 10, (), MainPanel.TIME_JOB_TAG)
        
        self.post_key = atomic.AtomicUnit(0)
        self.post_lock = Lock()
        
        # Scheduler flag. If a user tocheds any of buttons that belong to the scheduler then this flad turns True
        self.sched = atomic.AtomicUnit(False)
        
        self.job_post_timestamp = atomic.AtomicUnit(None)
        
        self.HideScheduler()
        
        # Makink mouse cursor invisible
        if config.IS_CURSOR_HIDDEN:
            cursor = wx.StockCursor(wx.CURSOR_BLANK)
            self.SetCursor(cursor)
    def _dummy_(self, event):
        pass
    # Increase time when placing a scheduled/delayed job
    def timeUp(self, event):
        # Set Scheduler key
        self.sched.set(True)
        # Remove POST_JOB
        self.parent.SC.rm(MainPanel.POST_JOB_TAG)
        # Remove TIME_JOB
        self.parent.SC.rm(MainPanel.TIME_JOB_TAG)
        if self.delay_seconds < 60*60*24:
            self.delay_seconds += 60 * self.time_up_b.ratio.get()
            res = timestamp(fmt=MainPanel.TIME_FORMAT, t=self.itime + self.delay_seconds)
            ymd, hm = res.split(' ')
            self.time_val.set(hm)
            self.time.setText(self.time_val.get())
    # Decrease time when placing a scheduled/delayed job
    def timeDown(self, event):
        # Set Scheduler key
        self.sched.set(True)
        # Remove POST_JOB
        self.parent.SC.rm(MainPanel.POST_JOB_TAG)
        # Remove TIME_JOB
        self.parent.SC.rm(MainPanel.TIME_JOB_TAG)
        if self.delay_seconds > 0:
            self.delay_seconds -= 60 * self.time_down_b.ratio.get()
            res = timestamp(fmt=MainPanel.TIME_FORMAT, t=self.itime + self.delay_seconds)
            ymd, hm = res.split(' ')
            self.time_val.set(hm)
            self.time.setText(self.time_val.get())
    # Repetative(scheduled) job
    def onRepeat(self):
        # Set Scheduler key
        self.sched.set(True)
        self.parent.SC.rm(MainPanel.POST_JOB_TAG)
    def onPost(self):
        self.parent.SC.rm(MainPanel.POST_JOB_TAG)
        self._post_()
        self.HideScheduler()
        # ReEnter the TIME_JOB
        self.parent.SC.enter(self.TimeJob, 10, (), MainPanel.TIME_JOB_TAG)
        self.sched.set(False)
        self.delay_seconds = 0
    # Time job. Used as a dedicated thread. If a client is connected to the server then the time is synced with the server
    # otherwise the time is taken fron the local device that is running the thermostat GUI panel (this code)
    def TimeJob(self):
        fmt = MainPanel.TIME_FORMAT
        # Check if the system is connected
        if self.parent.TI.sysint != None:
            try:
                self.itime = self.parent.TI.sysint.execute(time.time)
                self.strptime = timestamp(fmt=fmt, t=self.itime)
                ymd, hm = self.strptime.split(' ')
            except UI.UIError as err:
                ShowWarn(self, "Could not synchronize time with the system server. Display local time.")
                self.itime = time.time()
                self.strptime = timestamp(fmt=fmt, t=self.itime)
                ymd, hm = self.strptime.split(' ')
        else:
            self.itime = time.time()
            self.strptime = timestamp(fmt=fmt)
            ymd, hm = self.strptime.split(' ')
        self.parent.upper_panel.date.setText(ymd)
        self.time_val.set(hm)
        self.time.setText(self.time_val.get())
    def ShowScheduler(self):
        self.time_up_b.Show()
        self.time_down_b.Show()
        self.repeat_b.Show()
        self.post_b.Show()
        self.mode_label.Show()
        self.fan_label.Show()
    def HideScheduler(self):
        self.time_up_b.Hide()
        self.time_down_b.Hide()
        self.repeat_b.Hide()
        self.post_b.Hide()
        self.mode_label.Hide()
        self.fan_label.Hide()
    def postJob(self):
        token = 0
        self.post_lock.acquire()
        if self.post_key.get() == 0:
            self.post_key.inc(1)
            token = self.post_key.get()
        self.post_lock.release()
        if token == 1:
            self.parent.SC.rm(MainPanel.POST_JOB_TAG)
            self.post_key.set(0)
            self.HideScheduler()
            wx.PostEvent(self, MainPanel.POST_JOB())
    def _post_(self, event=None):
        if self.parent.TI.sysint != None:
            if self.parent.TI.nm_hvac != None:
                MyFrame.GLOCK.acquire()
                try:
                    # Determin whether a repetative job is being scheduled
                    if self.repeat_b.state == ToggleButton.STATE_ON:
                        period = 24*60*60
                    else:
                        period = 0
                    # Determining the mode for a HVAC
                    if self.parent.lower_panel.heatButton.state == ToggleButton.STATE_ON:
                        hvac_mode = ics_proto.HEAT
                    elif self.parent.lower_panel.coolButton.state == ToggleButton.STATE_ON:
                        hvac_mode = ics_proto.COOL
                    elif self.parent.lower_panel.climButton.state == ToggleButton.STATE_ON:
                        hvac_mode = ics_proto.CLIM
                    else:
                        hvac_mode = ics_proto.OFF
                    
                    # Determining wether the fan is on
                    if self.parent.lower_panel.fanButton.state == ToggleButton.STATE_ON:
                        hvac_fan = ics_proto.ON
                    else:
                        hvac_fan = ics_proto.AUTO
                    
                    # Determining start time for the upcoming job
                    ts = self.itime + self.delay_seconds
                    
                    
                    # BEGIN of Troublesome code
                    ## If a delayed job has been submitted then the interface must revert to its previous state
                    ### This code is not working properly
                    #~ if self.delay_seconds > 0:
                        #~ print "Submitting delayed job. Syncronization required!"
                        #~ self.parent.SC.resetWaitFor(MyFrame.GET_ESSENTIALS)
                    # END of Troublesome code
                    
                    args = (self.parent.TI.auth_id, self.parent.TI.username, self.parent.TI.pass_hash, ts, period, str(self.parent.TI.nm_hvac.hvac_id), hvac_fan, hvac_mode, self.t_val.get(), config.DELTA)
                    print args
                    new_ts = self.parent.TI.sysint.execute('user_interface.CLIENT.postJob', *args)
                    #~ print "%"*100
                    #~ print new_ts
                    #~ print "%"*100
                    self.job_post_timestamp.set( new_ts )
                    self.parent.SC.resetWaitFor(MyFrame.GET_ESSENTIALS)
                except UI.UIError as err:
                    ShowError(self, err.msg)
                finally:
                    MyFrame.GLOCK.release()
            else:
                ShowError(self, "No HVAC set to monitor. An HVAC must be set to active in order to be able posting jobs")
        else:
            ShowError(self, "Remote system is not connected.")
    def onUp(self, event):
        if self.t_val.get() < config.TEMP_MAX:
            self.ShowScheduler()
            self.t_val.inc(max(1, 1 * self.temp_up_b.ratio.get()/MainPanel.ACCEL_ADJUSTMENT))
            if self.t_val.get() > config.TEMP_MAX:
                self.t_val.set(config.TEMP_MAX)
            self.t_ctrl.setText(str(self.t_val.get()))
            if self.sched.get() == False:
                self.parent.SC.rm(MainPanel.POST_JOB_TAG)
                self.parent.SC.enter(self.postJob, config.SUBMISSION_DELAY, (), MainPanel.POST_JOB_TAG, config.SUBMISSION_DELAY)
    def onDown(self, event):
        if self.t_val.get() > config.TEMP_MIN:
            self.ShowScheduler()
            self.t_val.dec(max(1, 1 * self.temp_up_b.ratio.get()/MainPanel.ACCEL_ADJUSTMENT))
            if self.t_val.get() < config.TEMP_MIN:
                self.t_val.set(config.TEMP_MIN)
            self.t_ctrl.setText(str(self.t_val.get()))
            if self.sched.get() == False:
                self.parent.SC.rm(MainPanel.POST_JOB_TAG)
                self.parent.SC.enter(self.postJob, config.SUBMISSION_DELAY, (), MainPanel.POST_JOB_TAG, config.SUBMISSION_DELAY)
    def onChangeLowerPanel(self, event=None):
        # Determining the mode for a HVAC
        ModeText = {0:"OFF", 1:"CLIM", 2:"COOL", 3:"HEAT"}
        FanText = {5:"FAN AUTO", 4:"FAN ON"}
        if event >= 0 and event <= 3:
            self.mode_label.setText(ModeText[event])
        elif event >= 4 and event <= 5:
            self.fan_label.setText(FanText[event])
        self.ShowScheduler()
        if self.sched.get() == False:
            self.parent.SC.rm(MainPanel.POST_JOB_TAG)
            self.parent.SC.enter(self.postJob, config.SUBMISSION_DELAY, (), MainPanel.POST_JOB_TAG, config.SUBMISSION_DELAY)
    def Refresh(self):
        try:
            MyFrame.GLOCK.acquire()
            self.t_ind
        except UI.UIError as err:
            print err
            self.parent.parent.upper_panel.setStatusLights(0)
            self.parent.parent.info_panel.Unavailable()
            self.parent.parent.settings_panel.Unavailable()
        finally:
            MyFrame.GLOCK.release()

class UpperPanel(CustomPanel):
    
    SIZE = (MainPanel.SIZE[0],SHARED_VARIABLE_FOR_UPPER_PANEL_Y_SIZE)
    POS = (0,0)
    BG = config.UP['OUT']
    X_MARGIN = 75
    Y_MARGIN = 14
    FONT_SIZE = 14
    FONT_COLOR = (255,255,255)
    
    '''Attributes for the panel'''
    ICON_HEAT = 'ICON_HEAT'
    ICON_COOL = 'ICON_COOL'
    ICON_FAN = 'ICON_FAN'
    ICON_Y_CORRECTION = -6

    ICON_DICT = { ICON_HEAT:('heat_on.png',(37,37)),
                    ICON_COOL:('ac_on.png',(37,37)),
                    ICON_FAN:('fan_on.png',(37,37))  }

    STATUS_ICON_SIZE = (15,15)

    STATUS_ACTIVE = 'STATUS_ACTIVE'
    STATUS_INACTIVE = 'STATUS_INACTIVE'

    STATUS_DICT = { STATUS_ACTIVE:'status_active.png',
                    STATUS_INACTIVE:'status_unactive.png' }

    LABEL_SYSTEM = 'SYSTEM'
    LABEL_HVAC = 'HVAC'
    LABEL_SENSOR = 'SENSOR'
    
    def __init__(self, frame):
        self.parent = frame
        super(UpperPanel, self).__init__(self.parent, -1, pos=UpperPanel.POS, size=UpperPanel.SIZE, bg_rpath=UpperPanel.BG)
        spacing = 10
        pos = 0
        self.icon_heat = StatusIcon(self, UpperPanel.ICON_DICT[UpperPanel.ICON_HEAT][0], size=UpperPanel.ICON_DICT[UpperPanel.ICON_HEAT][1], pos=(UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN + UpperPanel.ICON_Y_CORRECTION))
        pos += UpperPanel.ICON_DICT[UpperPanel.ICON_HEAT][1][0] + spacing
        self.icon_fan  = StatusIcon(self, UpperPanel.ICON_DICT[UpperPanel.ICON_FAN ][0], size=UpperPanel.ICON_DICT[UpperPanel.ICON_FAN ][1], pos=(UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN + UpperPanel.ICON_Y_CORRECTION))
        pos += UpperPanel.ICON_DICT[UpperPanel.ICON_FAN ][1][0] + spacing
        self.icon_cool = StatusIcon(self, UpperPanel.ICON_DICT[UpperPanel.ICON_COOL][0], size=UpperPanel.ICON_DICT[UpperPanel.ICON_COOL][1], pos=(UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN + UpperPanel.ICON_Y_CORRECTION))
        pos = 180
        uppFont = wx.Font(UpperPanel.FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self.label_SYSTEM = wx.StaticText(self, -1, UpperPanel.LABEL_SYSTEM, pos=(UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN))
        self.label_SYSTEM.SetFont(uppFont)
        self.label_SYSTEM.SetForegroundColour(UpperPanel.FONT_COLOR)
        pos += len(UpperPanel.LABEL_SYSTEM) * UpperPanel.FONT_SIZE + spacing
        self.status_SYSTEM = StatusLight(self, UpperPanel.STATUS_DICT[UpperPanel.STATUS_ACTIVE], UpperPanel.STATUS_DICT[UpperPanel.STATUS_INACTIVE], UpperPanel.STATUS_ICON_SIZE, (UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN + (UpperPanel.STATUS_ICON_SIZE[1]/4)))
        pos += UpperPanel.STATUS_ICON_SIZE[0] + spacing
        
        pos += spacing
        self.label_HVAC = wx.StaticText(self, -1, UpperPanel.LABEL_HVAC, pos=(UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN))
        self.label_HVAC.SetFont(uppFont)
        self.label_HVAC.SetForegroundColour(UpperPanel.FONT_COLOR)
        pos += len(UpperPanel.LABEL_HVAC) * UpperPanel.FONT_SIZE + spacing
        self.status_HVAC = StatusLight(self, UpperPanel.STATUS_DICT[UpperPanel.STATUS_ACTIVE], UpperPanel.STATUS_DICT[UpperPanel.STATUS_INACTIVE], UpperPanel.STATUS_ICON_SIZE, (UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN + (UpperPanel.STATUS_ICON_SIZE[1]/4)))
        pos += UpperPanel.STATUS_ICON_SIZE[0] + spacing
        
        pos += spacing
        self.label_SENSOR = wx.StaticText(self, -1, UpperPanel.LABEL_SENSOR, pos=(UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN))
        self.label_SENSOR.SetFont(uppFont)
        self.label_SENSOR.SetForegroundColour(UpperPanel.FONT_COLOR)
        pos += len(UpperPanel.LABEL_SENSOR) * UpperPanel.FONT_SIZE + spacing
        self.status_SENSOR = StatusLight(self, UpperPanel.STATUS_DICT[UpperPanel.STATUS_ACTIVE], UpperPanel.STATUS_DICT[UpperPanel.STATUS_INACTIVE], UpperPanel.STATUS_ICON_SIZE, (UpperPanel.X_MARGIN + pos, UpperPanel.Y_MARGIN + (UpperPanel.STATUS_ICON_SIZE[1]/4)))
        pos += UpperPanel.STATUS_ICON_SIZE[0] + spacing
        
        
        # Date
        pos += 100
        self.date = DynamicText(self, (pos, UpperPanel.Y_MARGIN), '--|--|--', 14, style=wx.BOLD, color='white', stroke=0)
        
        # Hiding all the icons as the starting state is the "off" state
        self.icon_fan.Hide()
        self.icon_heat.Hide()
        self.icon_cool.Hide()
    
    def setStatusIcons(self, mask):
        if mask < 0 or mask > 7:
            raise ValueError("parameter 'mask' can only be in the range of 0-7")
        if mask & 1:
            self.icon_heat.Show()
        else:
            self.icon_heat.Hide()
        if mask & 2:
            self.icon_fan.Show()
        else:
            self.icon_fan.Hide()
        if mask & 4:
            self.icon_cool.Show()
        else:
            self.icon_cool.Hide()
    def setStatusLights(self, mask):
        if mask < 0 or mask > 7:
            raise ValueError("parameter 'mask' can only be in the range of 0-7")
        if mask & 1:
            self.status_SYSTEM.SwitchOn()
        else:
            self.status_SYSTEM.SwitchOff()
        if mask & 2:
            self.status_HVAC.SwitchOn()
        else:
            self.status_HVAC.SwitchOff()
        if mask & 4:
            self.status_SENSOR.SwitchOn()
        else:
            self.status_SENSOR.SwitchOff()

class LowerPanel(CustomPanel):
    
    SIZE = (MainPanel.SIZE[0],120)
    POS = (0,MainPanel.SIZE[1]-SIZE[1])
    BG = config.LP['OUT']
    X_MARGIN = 75
    Y_MARGIN = 10

    '''Attributes for the panel'''
    
    def __init__(self, frame):
        self.parent = frame
        super(LowerPanel, self).__init__(self.parent, -1, pos=LowerPanel.POS, size=LowerPanel.SIZE, bg_rpath=LowerPanel.BG)
        spacing = 20
        pos = 0
        self.climButton = ToggleButton(self, B_DICT[B_CLIM_DOWN], B_DICT[B_CLIM_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.heatButton = ToggleButton(self, B_DICT[B_HEAT_DOWN], B_DICT[B_HEAT_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.coolButton = ToggleButton(self, B_DICT[B_COOL_DOWN], B_DICT[B_COOL_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.fanButton = ToggleButton(self, B_DICT[B_FAN_DOWN], B_DICT[B_FAN_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.settingsButton = ToggleButton(self, B_DICT[B_SETTINGS_DOWN], B_DICT[B_SETTINGS_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        self.settingsButton.setActionOnPressed(self.parent.parent.settings_panel.Show)
        self.settingsButton.setActionOnUnpressed(self.parent.parent.settings_panel.Hide)
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.infoButton = ToggleButton(self, B_DICT[B_INFO_DOWN], B_DICT[B_INFO_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        self.infoButton.setActionOnPressed(self.parent.parent.info_panel.Show)
        self.infoButton.setActionOnUnpressed(self.parent.parent.info_panel.Hide)
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.loginButton = ToggleButton(self, B_DICT[B_USER_DOWN], B_DICT[B_USER_UP], ROUND_BUTTON_SIZE, (LowerPanel.X_MARGIN + pos, LowerPanel.Y_MARGIN))
        pos += ROUND_BUTTON_SIZE[0] + spacing
        self.loginButton.setActionOnPressed(self.parent.parent.connection_panel.Show)
        self.loginButton.setActionOnUnpressed(self.parent.parent.connection_panel.Hide)
        
        # Setting up the conflicting buttons so only one of them can be pressed at a time:
        # 1 Group: Climate Control; Heat; Cool
        self.climButton.setConflictingButton(self.heatButton, True)
        self.climButton.setConflictingButton(self.coolButton, True)
        self.heatButton.setConflictingButton(self.coolButton, True)
        self.heatButton.setConflictingButton(self.climButton, True)
        self.coolButton.setConflictingButton(self.climButton, True)
        self.coolButton.setConflictingButton(self.heatButton, True)
        
        # 2 Group Login, Settings, Info
        self.settingsButton.setConflictingButton(self.infoButton, False)
        self.settingsButton.setConflictingButton(self.loginButton, False)
        self.infoButton.setConflictingButton(self.loginButton, False)
        self.infoButton.setConflictingButton(self.settingsButton, False)
        self.loginButton.setConflictingButton(self.settingsButton, False)
        self.loginButton.setConflictingButton(self.infoButton, False)
        
        # Binding events for heat cool climate fan buttons
        self.climButton.setActionOnPressed(self.parent.parent.main_panel.onChangeLowerPanel, 1)
        self.climButton.setActionOnUnpressed(self.parent.parent.main_panel.onChangeLowerPanel, 0)
        self.coolButton.setActionOnPressed(self.parent.parent.main_panel.onChangeLowerPanel, 2)
        self.coolButton.setActionOnUnpressed(self.parent.parent.main_panel.onChangeLowerPanel, 0)
        self.heatButton.setActionOnPressed(self.parent.parent.main_panel.onChangeLowerPanel, 3)
        self.heatButton.setActionOnUnpressed(self.parent.parent.main_panel.onChangeLowerPanel, 0)
        self.fanButton.setActionOnPressed(self.parent.parent.main_panel.onChangeLowerPanel, 4)
        self.fanButton.setActionOnUnpressed(self.parent.parent.main_panel.onChangeLowerPanel, 5)

class ConnectionPanel(CustomPanel):
    
    SIZE = (MainPanel.SIZE[0], MainPanel.SIZE[1] - UpperPanel.SIZE[1] - LowerPanel.SIZE[1])
    POS = (0, UpperPanel.POS[1] + UpperPanel.SIZE[1])
    BG = None
    X_MARGIN = 15
    Y_MARGIN = 20
    FONT_SIZE = 14
    FONT_COLOR = (0,0,0)
    HINT_FONT_SIZE = 8
    HINT_FONT_COLOR = (255,0,0)
    TITLE_FONT_SIZE = 20
    TITLE_FONT_COLOR = (0,0,0)

    ''' Attributes for the panel'''
    Y_FACTOR = 0.5
    TITLE = 'LOGIN/CONNECTION'
    USERNAME = {'LABEL':'Username:', 'FIELD':(FONT_SIZE*16,int(FONT_SIZE/Y_FACTOR)), 'HINT':'100 characters max.'}
    PASSWORD = {'LABEL':'Password:', 'FIELD':(FONT_SIZE*16,int(FONT_SIZE/Y_FACTOR)), 'HINT':'100 characters max.'}
    HOST = {'LABEL':'Host:    ', 'FIELD':(FONT_SIZE*16,int(FONT_SIZE/Y_FACTOR)), 'HINT':'Must be a valid IP address or host name (100 characters max.)'}
    PORT = {'LABEL':'Port:    ', 'FIELD':(FONT_SIZE*4,int(FONT_SIZE/Y_FACTOR)), 'HINT':'Acceptabple range of values: 0-65535'}
    
    CONNECT_B = {'LABEL':'Connect', 'SIZE':(140,40)}
    DISCONNECT_B = {'LABEL':'Disconnect', 'SIZE':(140,40)}
    EXIT_B = {'LABEL':'Exit', 'SIZE':(140,40)}
    
    CRED_FILE = config.CRED_FILE
    SEPARATOR = ','
    
    def __init__(self, frame):
        self.parent = frame
        super(ConnectionPanel, self).__init__(self.parent, -1, size=ConnectionPanel.SIZE, pos=ConnectionPanel.POS, bg_rpath=ConnectionPanel.BG)
        spacing = 10
        xpos = ypos = 0 
        Font = wx.Font(ConnectionPanel.FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        HintFont = wx.Font(ConnectionPanel.HINT_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        TitleFont = wx.Font(ConnectionPanel.TITLE_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        
        # Title
        self.title = wx.StaticText(self, -1, ConnectionPanel.TITLE, pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.title.SetForegroundColour(ConnectionPanel.TITLE_FONT_COLOR)
        self.title.SetFont(TitleFont)
        ypos += 6 * spacing
        # Host field
        self.system_label_host = wx.StaticText(self, -1, ConnectionPanel.HOST['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_label_host.SetForegroundColour(ConnectionPanel.FONT_COLOR)
        self.system_label_host.SetFont(Font)
        xpos += len(ConnectionPanel.HOST['LABEL']) * ConnectionPanel.FONT_SIZE + spacing 
        self.system_field_host = wx.TextCtrl(self, pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.HOST['FIELD'])
        self.system_field_host.SetMaxLength(100)
        xpos += ConnectionPanel.HOST['FIELD'][0] + spacing 
        self.system_hint_host = wx.StaticText(self, -1, ConnectionPanel.HOST['HINT'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_hint_host.SetForegroundColour(ConnectionPanel.HINT_FONT_COLOR)
        self.system_hint_host.SetFont(HintFont)
        self.system_hint_host.Hide()
        ypos += 4 * spacing
        xpos = 0
        # Port field
        self.system_label_port = wx.StaticText(self, -1, ConnectionPanel.PORT['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_label_port.SetForegroundColour(ConnectionPanel.FONT_COLOR)
        self.system_label_port.SetFont(Font)
        xpos += len(ConnectionPanel.PORT['LABEL']) * ConnectionPanel.FONT_SIZE + spacing 
        self.system_field_port = wx.TextCtrl(self, pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.PORT['FIELD'])
        self.system_field_port.SetMaxLength(5)
        xpos += ConnectionPanel.PORT['FIELD'][0] + spacing 
        self.system_hint_port = wx.StaticText(self, -1, ConnectionPanel.PORT['HINT'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_hint_port.SetForegroundColour(ConnectionPanel.HINT_FONT_COLOR)
        self.system_hint_port.SetFont(HintFont)
        ypos += 4 * spacing
        xpos = 0
        # Username field
        self.system_label_username = wx.StaticText(self, -1, ConnectionPanel.USERNAME['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_label_username.SetForegroundColour(ConnectionPanel.FONT_COLOR)
        self.system_label_username.SetFont(Font)
        xpos += len(ConnectionPanel.USERNAME['LABEL']) * ConnectionPanel.FONT_SIZE + spacing 
        self.system_field_username = wx.TextCtrl(self, pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.USERNAME['FIELD'])
        self.system_field_username.SetMaxLength(100)
        xpos += ConnectionPanel.USERNAME['FIELD'][0] + spacing 
        self.system_hint_username = wx.StaticText(self, -1, ConnectionPanel.USERNAME['HINT'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_hint_username.SetForegroundColour(ConnectionPanel.HINT_FONT_COLOR)
        self.system_hint_username.SetFont(HintFont)
        ypos += 4 * spacing
        xpos = 0
        # Password field
        self.system_label_password = wx.StaticText(self, -1, ConnectionPanel.PASSWORD['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_label_password.SetForegroundColour(ConnectionPanel.FONT_COLOR)
        self.system_label_password.SetFont(Font)
        xpos += len(ConnectionPanel.PASSWORD['LABEL']) * ConnectionPanel.FONT_SIZE + spacing 
        self.system_field_password = wx.TextCtrl(self, pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.PASSWORD['FIELD'], style=wx.TE_PASSWORD)
        self.system_field_password.SetMaxLength(100)
        xpos += ConnectionPanel.PASSWORD['FIELD'][0] + spacing 
        self.system_hint_password = wx.StaticText(self, -1, ConnectionPanel.PASSWORD['HINT'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos))
        self.system_hint_password.SetForegroundColour(ConnectionPanel.HINT_FONT_COLOR)
        self.system_hint_password.SetFont(HintFont)
        ypos += 4 * spacing
        xpos = 0
        # Connect button
        self.system_connect_b = wx.Button(self, -1, label=ConnectionPanel.CONNECT_B['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.CONNECT_B['SIZE'])
        self.system_connect_b.Bind(wx.EVT_BUTTON, self.onConnect)
         # DisConnect button
        self.system_disconnect_b = wx.Button(self, -1, label=ConnectionPanel.DISCONNECT_B['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.DISCONNECT_B['SIZE'])
        self.system_disconnect_b.Bind(wx.EVT_BUTTON, self.onDisconnect)
        self.system_disconnect_b.Hide()
        # Exit button
        xpos += max(ConnectionPanel.CONNECT_B['SIZE'][0], ConnectionPanel.DISCONNECT_B['SIZE'][0]) + spacing
        self.system_exit_b = wx.Button(self, -1, label=ConnectionPanel.EXIT_B['LABEL'], pos=(ConnectionPanel.X_MARGIN + xpos, ConnectionPanel.Y_MARGIN + ypos), size=ConnectionPanel.EXIT_B['SIZE'])
        self.system_exit_b.Bind(wx.EVT_BUTTON, self.parent.parent.OnClose)
        
        # Hide hints for the time being
        self.Hints(0)
        
        # Bind the Enter key to work as Connect button 
        self.control_chain = [self.system_field_username, self.system_field_password, self.system_field_host, self.system_field_port, self.system_connect_b]
        self.control_index = 0
        self.system_connect_b.Bind(wx.EVT_KEY_UP, self.onEnter)
        self.system_field_username.Bind(wx.EVT_KEY_UP, self.onEnter)
        self.system_field_password.Bind(wx.EVT_KEY_UP, self.onEnter)
        self.system_field_host.Bind(wx.EVT_KEY_UP, self.onEnter)
        self.system_field_port.Bind(wx.EVT_KEY_UP, self.onEnter)
        
    def Hints(self, mask):
        if mask < 0 or mask > 15:
            raise ValueError("parameter 'mask' can only be in the range of 0-15")
        if mask & 1:
            self.system_hint_host.Show()
        else:
            self.system_hint_host.Hide()
        if mask & 2:
            self.system_hint_port.Show()
        else:
            self.system_hint_port.Hide()
        if mask & 4:
            self.system_hint_username.Show()
        else:
            self.system_hint_username.Hide()
        if mask & 8:
            self.system_hint_password.Show()
        else:
            self.system_hint_password.Hide()
    # On press Enter key
    def onEnter(self, evt):
        if evt.GetKeyCode() == wx.WXK_RETURN:
            #~ if self.control_index == len(self.control_chain):
                #~ self.control_index = 0
            if self.system_connect_b.IsShown():
                self.onConnect(None)
    # On connect
    def onConnect(self, evt):
        try:
            v1,v2,v3,v4 = self._collectFields()
            try:
                self.control_object.connect(v1,v2,v3,v4)
                self.system_disconnect_b.Disable()
                self.system_connect_b.Hide()
                self.system_disconnect_b.Show()
                self.Hints(0)
                self.parent.parent.SC.enter(self.query_loop, config.Q_INTERVAL, (), MyFrame.GET_ESSENTIALS)
                MyFrame.LAYOUT_EVENT_1.event().wait(10)
                if MyFrame.LAYOUT_EVENT_1.get() != 0:
                    self.parent.parent.info_panel.Available()
                    self.parent.parent.settings_panel.Available()
                    self.system_disconnect_b.Enable()
                else:
                    raise UI.UIError('Layout Event 1 timed out')
                self.parent.parent.SC.resetWaitFor(MainPanel.TIME_JOB_TAG)
            except UI.UIError as err:
                self.Hints(15)
                print err
        except ValueError as err:
            print err
            self.Hints(15)
    def query_loop(self):
        '''1. Status lights for HVAC and SENSORS should ideally be controlled solely from within the query_loop 
              because they indicate the connection state between the coresponding components and the system
              
              '''
        is_error = False
        try:
            MyFrame.GLOCK.acquire()
            # Query the server to get essential data for the thermostat
            self.control_object.query_essentials()
            # Lit up the SYSTEM status light
            self.parent.parent.upper_panel.status_SYSTEM.SwitchOn()
            # CHeck if there is a HVAC set to active
            if self.parent.parent.TI.nm_hvac != None:
                # Make sure it is in the list of currently set HVACs
                if self.parent.parent.TI.nm_hvac.hvac_id in self.parent.parent.TI.cur_hvacs:
                    # Turn on the HVAC status light
                    self.parent.parent.upper_panel.status_HVAC.SwitchOn()
                    # Update the Currently monitored HVAC
                    self.parent.parent.TI.nm_hvac = self.parent.parent.TI.cur_hvacs[self.parent.parent.TI.nm_hvac.hvac_id]
                    # Make sure that the associated with active HVAC sensor is in the list of currently set sensors
                    if self.parent.parent.TI.nm_hvac.sensor_id in self.parent.parent.TI.cur_sensors:
                        # Turn on the SENSOR status light on
                        self.parent.parent.upper_panel.status_SENSOR.SwitchOn()
                    else:
                        self.parent.parent.upper_panel.status_SENSOR.SwitchOff()
                else:
                    self.parent.parent.upper_panel.status_HVAC.SwitchOff()
                
                # Syncing the upperpanel status icons with actual values from the active HVAC
                if self.parent.parent.TI.nm_hvac.fan:
                    self.parent.parent.upper_panel.icon_fan.Show()
                else:
                    self.parent.parent.upper_panel.icon_fan.Hide()
                if self.parent.parent.TI.nm_hvac.heat:
                    self.parent.parent.upper_panel.icon_heat.Show()
                else:
                    self.parent.parent.upper_panel.icon_heat.Hide()
                if self.parent.parent.TI.nm_hvac.cool:
                    self.parent.parent.upper_panel.icon_cool.Show()
                else:
                    self.parent.parent.upper_panel.icon_cool.Hide()
               
                # Get the latest current job update
                j = self.parent.parent.TI.SyncJob()
                if j != None:
                     # Synchronize the job details
                    jd = "Job posted by {0} @ {1}".format(j.publisher, j.start_time)
                else:
                    jd = "No job set"
                self.parent.parent.main_panel.j_detail.setText(jd)
                
                ''' All we have to do is to compare the job posting times of last job that was posted by a current 
                    client and another one or, by setting DELAYED JOB'''
                if self.parent.parent.main_panel.job_post_timestamp.get() != None:
                    try:
                        t_diff = (datetime.strptime(self.parent.parent.main_panel.job_post_timestamp.get(), config.DATE_FORMAT) - datetime.strptime(j.start_time, config.DATE_FORMAT)).total_seconds()
                        print "$"*100
                        print t_diff
                        print "$"*100
                    except AttributeError:
                        t_diff = 0.0
                    # Update post_timestamp
                    try:
                        self.parent.parent.main_panel.job_post_timestamp.set(j.start_time)
                        if t_diff != 0:
                            # Syncing the current job with the interface layout
                            if j.hvac_mode == ics_proto.CLIM:
                                self.parent.parent.lower_panel.climButton.press(True)
                            elif j.hvac_mode == ics_proto.COOL:
                                self.parent.parent.lower_panel.coolButton.press(True)
                            elif j.hvac_mode == ics_proto.HEAT:
                                self.parent.parent.lower_panel.heatButton.press(True)
                            elif j.hvac_mode == ics_proto.OFF:
                                self.parent.parent.lower_panel.climButton.unpress(True)
                                self.parent.parent.lower_panel.coolButton.unpress(True)
                                self.parent.parent.lower_panel.heatButton.unpress(True)
                            else:
                                # This point should actually never be reached, therefore there is no certain exception type that handles that, but just a plain exception... Just in case 
                                raise Exception("Unallowed value {0} encountered. Acceptable values are {1}".format(j.hvac_mode, config.HVAC_MODES))
                            
                            if j.hvac_fan == ics_proto.ON:
                                self.parent.parent.lower_panel.fanButton.press(True)
                            elif j.hvac_fan == ics_proto.AUTO:
                                self.parent.parent.lower_panel.fanButton.unpress(True)
                            
                            # Also need to sync the temperature control
                            self.parent.parent.main_panel.t_val.set(j.hvac_temp)
                            self.parent.parent.main_panel.t_ctrl.setText(str(j.hvac_temp))
                            
                    # If job has been cancelled then...
                    except AttributeError:
                        self.parent.parent.lower_panel.climButton.unpress(True)
                        self.parent.parent.lower_panel.coolButton.unpress(True)
                        self.parent.parent.lower_panel.heatButton.unpress(True)
                        self.parent.parent.lower_panel.fanButton.unpress(True)
                        jd = "No job set"
                        self.parent.parent.main_panel.j_detail.setText(jd)
                        
                # We end up here when posting a CURRENT job, because t_diff == 0
                else:
                    # If no jobs have ever been posted from the current client, but there is a job set, then sync'ing is needed
                    if self.parent.parent.TI.job.get() != None:
                        print '='*50
                        print 'Initial job synchronization'
                        print '='*50
                        j = self.parent.parent.TI.jobs[self.parent.parent.TI.job.get().job_id]
                        if j.hvac_mode == ics_proto.CLIM:
                            self.parent.parent.lower_panel.climButton.press(True)
                        elif j.hvac_mode == ics_proto.COOL:
                            self.parent.parent.lower_panel.coolButton.press(True)
                        elif j.hvac_mode == ics_proto.HEAT:
                            self.parent.parent.lower_panel.heatButton.press(True)
                        elif j.hvac_mode == ics_proto.OFF:
                            self.parent.parent.lower_panel.climButton.unpress(True)
                            self.parent.parent.lower_panel.coolButton.unpress(True)
                            self.parent.parent.lower_panel.heatButton.unpress(True)
                        else:
                            # This point should actually never be reached, therefore there is no certain exception type that handles that, but just a plain exception... Just in case 
                            raise Exception("Unallowed value {0} encountered. Acceptable values are {1}".format(j.hvac_mode, config.HVAC_MODES))
                        
                        if j.hvac_fan == ics_proto.ON:
                            self.parent.parent.lower_panel.fanButton.press(True)
                        elif j.hvac_fan == ics_proto.AUTO:
                            self.parent.parent.lower_panel.fanButton.unpress(True)
                        
                        # Also need to sync the temperature control
                        self.parent.parent.main_panel.t_val.set(j.hvac_temp)
                        self.parent.parent.main_panel.t_ctrl.setText(str(j.hvac_temp))
                        
                        # If there is a active job is currently set, then sync the temperature with the GUI temperature control object
                        self.parent.parent.main_panel.t_ctrl.setText(str(self.parent.parent.TI.job.get().hvac_temp))
                        
                        # Update post_timestamp
                        self.parent.parent.main_panel.job_post_timestamp.set(j.start_time)
                    # If job has been cancelled then...
                    else:
                        self.parent.parent.lower_panel.climButton.unpress(True)
                        self.parent.parent.lower_panel.coolButton.unpress(True)
                        self.parent.parent.lower_panel.heatButton.unpress(True)
                        self.parent.parent.lower_panel.fanButton.unpress(True)
                
                # Fetch the temperature for the current HVAC
                try:
                    sensor = self.parent.parent.TI.cur_sensors[self.parent.parent.TI.nm_hvac.sensor_id]
                    s_info = self.parent.parent.TI.sensors[self.parent.parent.TI.nm_hvac.sensor_id]
                    # Obtain the python class
                    s_obj = unpic(s_info.stype)
                    if sensor.raw_data != None:
                        # Interprit raw data based on the sensor type defined in sensor.py
                        temp = s_obj.interprit(sensor.raw_data, config.TEMP_FLOOR)
                    else:
                        temp = '--'
                    self.parent.parent.main_panel.t_ind.setText(str(temp))
                except KeyError as err:
                    self.parent.parent.TI.nm_hvac = None
                    ShowError(self, "Could not retrieve sensor {0}".format(self.parent.parent.TI.nm_hvac.sensor_id))
                
            else: # No nm_hvac is set. Cancle out whatever is on
                pass
                self.parent.parent.upper_panel.status_HVAC.SwitchOff()
                self.parent.parent.upper_panel.status_SENSOR.SwitchOff()
                self.parent.parent.upper_panel.icon_fan.Hide()
                self.parent.parent.upper_panel.icon_heat.Hide()
                self.parent.parent.upper_panel.icon_cool.Hide()
                # Synchronize the job details
                jd = "No job set"
                self.parent.parent.main_panel.j_detail.setText(jd)
            
            # Once all operation are performed the layout for other panels gets set to accessible
            MyFrame.LAYOUT_EVENT_1.set(1)
            MyFrame.LAYOUT_EVENT_1.event().set()
            
        except UI.UIError as err:
            is_error = True
            print ">"*100
            print err
            print ">"*100
            #~ ShowError(self, err.msg) # This is the main suspect that causes the X server bug to occur
        finally:
            MyFrame.GLOCK.release()
        if is_error:
            SendEvent(self.system_disconnect_b, wx.EVT_BUTTON)
    def onDisconnect(self, evt):
        MyFrame.GLOCK.acquire()
        self.control_object.disconnect()
        MyFrame.GLOCK.release()
        MyFrame.LAYOUT_EVENT_1.set(0, True)
        self.parent.parent.info_panel.Unavailable()
        self.parent.parent.settings_panel.Unavailable()
        self.system_disconnect_b.Hide()
        self.system_connect_b.Show()
        self.parent.parent.SC.rm(MyFrame.GET_ESSENTIALS)
        self.parent.parent.upper_panel.setStatusLights(0)
    def _populateFields(self):
        try:
            self.system_field_host.ChangeValue(str(self.control_object.sysint.host))
            self.system_field_port.ChangeValue(str(self.control_object.sysint.port))
            self.system_field_username.ChangeValue(str(self.control_object.username))
        except AttributeError:
            try:
                v = CredMan.cred_load(ConnectionPanel.CRED_FILE)
                self.system_field_host.ChangeValue(v.host)
                self.system_field_port.ChangeValue(str(v.port))
                self.system_field_username.ChangeValue(v.username)
                self.system_field_password.ChangeValue(v.password)
            except UI.UIError as err:
                if err.getError() == UI.UIError.CREDENTIALS_ERROR:
                    pass
                else:
                    raise err
            except AttributeError as err:
                    pass
    def _collectFields(self):
        try:
            v1 = str(self.system_field_host.GetValue())
            try:
                v2 = int(self.system_field_port.GetValue())
                if v2 < 0 or v2 > 65535:
                    raise ValueError("Port value is beyond the allowd port range")
            except ValueError as err:
                raise ValueError("Port field is incorrect: {0}".format(err))
            v3 = str(self.system_field_username.GetValue())
            v4 = str(UI.sha512(self.system_field_password.GetValue()))
            if len(v1) == 0:
                raise ValueError("Host field is empty")
            if len(v3) == 0:
                raise ValueError("Username field is empty")
            creds = CredMan(v3, self.system_field_password.GetValue(), v1, v2, None)
            CredMan.cred_save(ConnectionPanel.CRED_FILE, creds)
            return v1, v2, v3, v4
        except ValueError as err:
            print err
            raise err
        finally:
            self.system_field_password.Clear()
    def Show(self):
        super(ConnectionPanel, self).Show()
        self._populateFields()
        

def text_tab(text, font_size, percentage=100):
    p = min(100, percentage)/100.0
    l = len(text)
    f = font_size
    return int(p*f*l)

class SettingsPanel(ScrollPanel):
    
    SIZE = (MainPanel.SIZE[0], MainPanel.SIZE[1] - UpperPanel.SIZE[1] - LowerPanel.SIZE[1])
    POS = (0, UpperPanel.POS[1] + UpperPanel.SIZE[1])
    BG = None
    X_MARGIN = 15
    Y_MARGIN = 20
    FONT_SIZE = 10
    FONT_COLOR = (0,0,0)
    IND_FONT_SIZE = 10
    IND_FONT_COLOR = (46,134,46)
    ERR_FONT_SIZE = 14
    ERR_FONT_COLOR = (255,0,0)
    TITLE_FONT_SIZE = 20
    TITLE_FONT_COLOR = (0,0,0)

    ''' Attributes for the panel'''
    P = 67
    SIZE_Y = 30
    SPACING = 10
    SEPARETOR = ':'
    
    '''Separator for a new havc cmd and new sensor cmd'''
    CMD_SEPARATOR = ':::'
    
    DEACT_B = {'LABEL':'Deactivate', 'SIZE':(75,SIZE_Y)}
    ACT_B = {'LABEL':'Activate', 'SIZE':(70,SIZE_Y)}
    DEL_B = {'LABEL':'Del', 'SIZE':(55,SIZE_Y)}
    SET_B = {'LABEL':'Set', 'SIZE':(55,SIZE_Y)}
    UNSET_B = {'LABEL':'Unset', 'SIZE':(60,SIZE_Y)}
    CANCEL_B = {'LABEL':'Cancel', 'SIZE':(65,SIZE_Y)}
    REG_B = {'LABEL':'Register', 'SIZE':(70,SIZE_Y)}
    DUMMY_B = {'LABEL':'', 'SIZE':(0,0)}
    # Sensor type combobox parameters. We make up the combobox to look loike a button in order to fit into our layout convention
    S_TYPE_CBOX = {'LABEL':'aaaaaaaaaa','SIZE':(150,SIZE_Y)}
    
    TITLE               = 'SETTINGS'
    ERROR = 'Error: connection to the system has not been done'
    
    NM            = {'LABEL':'Now monitoring:    ', 'CTRL1':DEACT_B, 'CTRL2':DUMMY_B}
    J             = {'LABEL':'Jobs:'              , 'CTRL1':CANCEL_B, 'CTRL2':DUMMY_B}
    A_HVACS       = {'LABEL':'Active HVACs:      ', 'CTRL1':ACT_B, 'CTRL2':UNSET_B}
    R_HVACS       = {'LABEL':'Registered HVACs:  ', 'CTRL1':SET_B, 'CTRL2':DEL_B}
    A_SENSORS     = {'LABEL':'Active sensors:    ', 'CTRL1':UNSET_B, 'CTRL2':DUMMY_B}
    R_SENSORS     = {'LABEL':'Registered sensors:', 'CTRL1':SET_B, 'CTRL2':DEL_B}
    NEW_HVAC      = {'LABEL':'Register HVAC:     ', 'CTRL1':REG_B, 'CTRL2':DUMMY_B}
    NEW_SENSOR    = {'LABEL':'Register SENSOR:   ', 'CTRL1':REG_B, 'CTRL2':S_TYPE_CBOX}
    LABELS = [NM, J, A_HVACS, R_HVACS, A_SENSORS, R_SENSORS, NEW_HVAC, NEW_SENSOR]
    
    H_DESCRIPTION_LABEL = 'host%port%username%password%path%cool_wattage%heat_wattage%cool_kwph%heat_kwph%description'
    S_DESCRIPTION_LABEL = 'host%port%username%password%path'
    
    Y_POS_CORRECTION = 7
    
    # Layout convention
    for i in LABELS:
        i['TAB'] = text_tab(i['LABEL'], FONT_SIZE, P)
        i['SIZE1'] = (SIZE[0]/2 - X_MARGIN - i['TAB'] - i['CTRL1']['SIZE'][0] - 2*SPACING - i['CTRL2']['SIZE'][0], SIZE_Y)
        i['SIZE2'] = (SIZE[0]   - X_MARGIN - i['TAB'] - i['CTRL1']['SIZE'][0] - 2*SPACING - i['CTRL2']['SIZE'][0], SIZE_Y)
    
    DATE_FIELD_SZ = (SIZE[0]/2 - 2.5*SPACING, SIZE_Y)
    CLEAN_BUTTON_SZ = (SIZE[0]/3 - 2*SPACING,SIZE_Y)
    
    AVAILABLE,  EVT_AVAILABLE  = newevent.NewEvent()
    UNAVAILABLE, EVT_UNAVAILABLE = newevent.NewEvent()
    
    def __init__(self, frame):
        self.parent = frame
        super(SettingsPanel, self).__init__(self.parent, -1, size=SettingsPanel.SIZE, pos=SettingsPanel.POS, bg_rpath=SettingsPanel.BG)
        
        # Bind panel availability events
        self.Bind(SettingsPanel.EVT_AVAILABLE, self.onAvailabale)
        self.Bind(SettingsPanel.EVT_UNAVAILABLE, self.onUnavailable)
        
        spacing = SettingsPanel.SPACING
        xpos = ypos = 0 
        Font = wx.Font(SettingsPanel.FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        IndFont = wx.Font(SettingsPanel.IND_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        ErrFont = wx.Font(InfoPanel.ERR_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        TitleFont = wx.Font(SettingsPanel.TITLE_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        
        # Dummy objects used to create sizer. Make changes at this time when everything works fine is not fasible. Therefore I will do it this way
        dummy = wx.StaticText(self, -1, " ", pos=(0,0))
        
        # Title
        self.title = wx.StaticText(self, -1, SettingsPanel.TITLE, pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos))
        self.title.SetForegroundColour(SettingsPanel.TITLE_FONT_COLOR)
        self.title.SetFont(TitleFont)
        ypos += 4 * spacing
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.title, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(hSizer, 0, wx.TOP, SettingsPanel.Y_MARGIN)
        
        # Error label
        self.error_label = wx.StaticText(self, -1, SettingsPanel.ERROR, pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos))
        self.error_label.SetForegroundColour(SettingsPanel.ERR_FONT_COLOR)
        self.error_label.SetFont(ErrFont)
        xpos = 0
        
        # "Now monitoring" label
        self.nm_label = wx.StaticText(self, -1, SettingsPanel.NM['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.nm_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.nm_label.SetFont(Font)
        xpos += SettingsPanel.NM['TAB']
        # Deactivate button
        self.deact_b = wx.Button(self, -1, label=SettingsPanel.NM['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0]/2 - SettingsPanel.NM['CTRL1']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.NM['CTRL1']['SIZE'])
        # Active HVAC indicator
        self.nm_indicator = DynamicText(self, (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION), SettingsPanel.NM['LABEL'], SettingsPanel.IND_FONT_SIZE, color=SettingsPanel.IND_FONT_COLOR)
        try:
            self.nm_indicator.setText(self.parent.parent.TI.sysint.nm_hvac)
        except AttributeError:
            self.nm_indicator.setText("None")
        # Jobs label
        xpos = SettingsPanel.SIZE[0]/2
        self.j_label = wx.StaticText(self, -1, SettingsPanel.J['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.j_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.j_label.SetFont(Font)
        xpos += SettingsPanel.J['TAB']
        # Jobs combobox
        self.jbox = wx.ComboBox(self, -1, '', (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.J['SIZE1'], ['1','2'])
        # Cancel button
        self.cancel_b = wx.Button(self, -1, label=SettingsPanel.J['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.J['CTRL1']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.J['CTRL1']['SIZE'])
        xpos = 0
        ypos += spacing*3
        
        # Registered HVAC label
        self.rh_label = wx.StaticText(self, -1, SettingsPanel.R_HVACS['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.rh_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.rh_label.SetFont(Font)
        xpos += SettingsPanel.R_HVACS['TAB']
        # Registered HVACs ComboBox
        self.rh_box = wx.ComboBox(self, -1, '', (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.R_HVACS['SIZE2'], ['1','2'])
        # HVAC set button
        self.h_set_b = wx.Button(self, -1, label=SettingsPanel.R_HVACS['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.R_HVACS['CTRL1']['SIZE'][0] - SettingsPanel.R_HVACS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.R_HVACS['CTRL1']['SIZE'])
        # HVAC del button
        self.h_del_b = wx.Button(self, -1, label=SettingsPanel.R_HVACS['CTRL2']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.R_HVACS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.R_HVACS['CTRL2']['SIZE'])
        ypos += spacing*3
        xpos = 0
        
        # Registered sensors label
        self.rs_label = wx.StaticText(self, -1, SettingsPanel.R_SENSORS['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.rs_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.rs_label.SetFont(Font)
        xpos += SettingsPanel.R_SENSORS['TAB']
        # Registered Sensors ComboBox
        self.rs_box = wx.ComboBox(self, -1, '', (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.R_SENSORS['SIZE2'], ['1','2'])
        # Sensor set button
        self.s_set_b = wx.Button(self, -1, label=SettingsPanel.R_SENSORS['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.R_SENSORS['CTRL1']['SIZE'][0] - SettingsPanel.R_SENSORS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.R_SENSORS['CTRL1']['SIZE'])
        # Sensor del button
        self.s_del_b = wx.Button(self, -1, label=SettingsPanel.R_SENSORS['CTRL2']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.R_SENSORS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.R_SENSORS['CTRL2']['SIZE'])
        ypos += spacing*3
        xpos = 0
        
        # Active(Current) HVAC label
        self.curh_label = wx.StaticText(self, -1, SettingsPanel.A_HVACS['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.curh_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.curh_label.SetFont(Font)
        xpos += SettingsPanel.A_HVACS['TAB']
        # Active(Current) HVACs ComboBox
        self.curh_box = wx.ComboBox(self, -1, '', (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.A_HVACS['SIZE2'], ['1','2'])
        # HVAC activate button
        self.h_act_b = wx.Button(self, -1, label=SettingsPanel.A_HVACS['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.A_HVACS['CTRL1']['SIZE'][0] - SettingsPanel.A_HVACS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.A_HVACS['CTRL1']['SIZE'])
        # HVAC unset button
        self.h_unset_b = wx.Button(self, -1, label=SettingsPanel.A_HVACS['CTRL2']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.A_HVACS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.A_HVACS['CTRL2']['SIZE'])
        ypos += spacing*3
        xpos = 0
        
        # Active(Current) sensors label
        self.curs_label = wx.StaticText(self, -1, SettingsPanel.A_SENSORS['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.curs_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.curs_label.SetFont(Font)
        xpos += SettingsPanel.A_SENSORS['TAB']
        # Registered Sensors ComboBox
        self.curs_box = wx.ComboBox(self, -1, '', (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.A_SENSORS['SIZE2'], ['1','2'])
        # Sensor unset button
        self.s_unset_b = wx.Button(self, -1, label=SettingsPanel.A_SENSORS['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.A_SENSORS['CTRL1']['SIZE'][0] - SettingsPanel.A_SENSORS['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.A_SENSORS['CTRL1']['SIZE'])
        ypos += spacing*3
        xpos = 0
        
        # New HVAC label
        self.new_hvac_label = wx.StaticText(self, -1, SettingsPanel.NEW_HVAC['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.new_hvac_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.new_hvac_label.SetFont(Font)
        xpos += SettingsPanel.NEW_HVAC['TAB']
        # New HVAC query line
        self.new_hvac_cmd = wx.ComboBox(self, -1, SettingsPanel.H_DESCRIPTION_LABEL, (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.NEW_HVAC['SIZE2'], ['1','2'])
        # Register button
        self.h_create_b = wx.Button(self, -1, label=SettingsPanel.NEW_HVAC['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.NEW_HVAC['CTRL1']['SIZE'][0] - SettingsPanel.NEW_HVAC['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.NEW_HVAC['CTRL1']['SIZE'])
        ypos += spacing*3
        xpos = 0
        
        # New Sensor label
        self.new_sensor_label = wx.StaticText(self, -1, SettingsPanel.NEW_SENSOR['LABEL'], pos=(SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos + SettingsPanel.Y_POS_CORRECTION))
        self.new_sensor_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.new_sensor_label.SetFont(Font)
        xpos += SettingsPanel.NEW_SENSOR['TAB']
        # New HVAC query line
        self.new_sensor_cmd = wx.ComboBox(self, -1, SettingsPanel.S_DESCRIPTION_LABEL, (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.NEW_SENSOR['SIZE2'], ['1','2'])
        # Sensor type compobox
        sensor_list = []
        for i in sensor.SENSORS:
            sensor_list.append(i.__name__)
        self.s_type_cb = wx.ComboBox(self, -1, 'Choose sensor', (SettingsPanel.SIZE[0] - SettingsPanel.NEW_SENSOR['CTRL1']['SIZE'][0] - SettingsPanel.NEW_SENSOR['CTRL2']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), SettingsPanel.NEW_SENSOR['CTRL2']['SIZE'], sensor_list)
        # Register button
        self.s_create_b = wx.Button(self, -1, label=SettingsPanel.NEW_SENSOR['CTRL1']['LABEL'], pos=(SettingsPanel.SIZE[0] - SettingsPanel.NEW_SENSOR['CTRL1']['SIZE'][0] - SettingsPanel.X_MARGIN, SettingsPanel.Y_MARGIN + ypos), size=SettingsPanel.NEW_SENSOR['CTRL1']['SIZE'])
        
        # Setting up history management
        hist_vSizer = wx.BoxSizer(wx.VERTICAL)
        # Label
        self.hist_m_label = wx.StaticText(self, -1, "History management:", pos=(0,0))
        self.hist_m_label.SetForegroundColour(SettingsPanel.FONT_COLOR)
        self.hist_m_label.SetFont(Font)
        ## pushing controls to a horizontal sizer
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.hist_m_label, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        hist_vSizer.Add(hSizer, 0, wx.TOP, SettingsPanel.Y_MARGIN)
        # From text field
        self.from_field = wx.TextCtrl(self, -1, timestamp(t=time.time()-(config.BACK_TIME * 24 * 3600)), pos=(0,0), size=SettingsPanel.DATE_FIELD_SZ)
        # To text field
        self.to_field = wx.TextCtrl(self, -1, timestamp(), pos=(0,0), size=SettingsPanel.DATE_FIELD_SZ)
        ## pushing controls to a horizontal sizer
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.from_field, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        hSizer.Add(self.to_field, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        hist_vSizer.Add(hSizer, 0, wx.TOP, SettingsPanel.SPACING)
        # Clean HVACs button
        self.cl_hvacs_b = wx.Button(self, -1, label="Clean HVAC history", pos=(0,0), size=SettingsPanel.CLEAN_BUTTON_SZ)
        # Clean sensors button
        self.cl_sensors_b = wx.Button(self, -1, label="Clean sensor history", pos=(0,0), size=SettingsPanel.CLEAN_BUTTON_SZ)
        # Clean jobs button
        self.cl_jobs_b = wx.Button(self, -1, label="Clean job history", pos=(0,0), size=SettingsPanel.CLEAN_BUTTON_SZ)
        ## pushing controls to a horizontal sizer
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.cl_hvacs_b, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        hSizer.Add(self.cl_sensors_b, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        hSizer.Add(self.cl_jobs_b, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        hist_vSizer.Add(hSizer, 0, wx.TOP, SettingsPanel.SPACING)
        
        # Adding the lowest element
        vSizer.Add(hist_vSizer, 0, wx.TOP, ypos)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(dummy, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        vSizer.Add(hSizer, 0, wx.TOP, SettingsPanel.SPACING)
        
        # Setting up the sizer
        self.SetSizer(vSizer)
        
        self.control_list = [
                            self.nm_label,
                            self.deact_b,
                            self.nm_indicator,
                            self.j_label,
                            self.jbox,
                            self.cancel_b,
                            self.rh_label,
                            self.rh_box,
                            self.h_set_b,
                            self.h_del_b,
                            self.rs_label,
                            self.rs_box,
                            self.s_set_b,
                            self.s_del_b,
                            self.curh_label,
                            self.curh_box,
                            self.h_act_b,
                            self.h_unset_b,
                            self.curs_label,
                            self.curs_box,
                            self.s_unset_b,
                            self.new_hvac_label,
                            self.new_hvac_cmd,
                            self.h_create_b,
                            self.new_sensor_label,
                            self.new_sensor_cmd,
                            self.s_type_cb,
                            self.s_create_b,
                            self.hist_m_label,
                            self.from_field,
                            self.to_field,
                            self.cl_hvacs_b,
                            self.cl_sensors_b,
                            self.cl_jobs_b ]
        
        # Binding actions on buttons
        B = {'DEACT':self.deact_b,
            'HACT':self.h_act_b,
            'CANCEL':self.cancel_b,
            'HSET':self.h_set_b,
            'HDEL':self.h_del_b,
            'SSET':self.s_set_b,
            'SDEL':self.s_del_b,
            'HUNSET':self.h_unset_b,
            'SUNSET':self.s_unset_b,
            'HNEW':self.h_create_b,
            'SNEW':self.s_create_b,
            'HHCL':self.cl_hvacs_b,
            'SHCL':self.cl_sensors_b,
            'JHCL':self.cl_jobs_b }
        
        for k,v in B.iteritems():
            v.Bind(wx.EVT_BUTTON, lambda event, key=k: self.onButton(event, key))
        
        self.Unavailable()
    def onButton(self, event, key):
        print key
        r_api = REMOTE_API
        if key == 'DEACT':
            # Remove all jobs for the given HVAC
            pass
            # Post the event that notifies the main panel to change the layout
            pass
            # Then remove the 'Now monitoring' HVAC
            if self.parent.parent.TI.nm_hvac != None:
                ShowInfo(self, 'HVAC {0} is now deactivated. All jobs associated with the HVAC were also cancelled.'.format(self.parent.parent.TI.nm_hvac.hvac_id))
                #~ self.parent.parent.upper_panel.status_HVAC.SwitchOff()
                #~ self.parent.parent.upper_panel.status_SENSOR.SwitchOff()
                self.parent.parent.TI.nm_hvac = None
            else:
                ShowError(self, 'No HVACs currently set to monitor.')
                return -1
        elif key == 'HACT':
            # Post the event that notifies the main panel to change the layout
            pass
            # Then set the 'Now monitoring' HVAC
            try:
                self.parent.parent.TI.nm_hvac = self.parent.parent.TI.cur_hvacs[self.curh_box.GetValue()]
                if self.parent.parent.TI.nm_hvac.hvac_id in self.parent.parent.TI.cur_hvacs:
                    #~ self.parent.parent.upper_panel.status_HVAC.SwitchOn()
                    if self.parent.parent.TI.nm_hvac.sensor_id in self.parent.parent.TI.cur_sensors:
                        #~ self.parent.parent.upper_panel.status_SENSOR.SwitchOn()
                        v = CredMan.cred_load(ConnectionPanel.CRED_FILE)
                        v.active_hvac = self.parent.parent.TI.nm_hvac.hvac_id
                        CredMan.cred_save(ConnectionPanel.CRED_FILE, v)
                    else:
                        #~ self.parent.parent.upper_panel.status_SENSOR.SwitchOff()
                        print self.parent.parent.TI.nm_hvac.sensor_id
                        print self.parent.parent.TI.cur_sensors
                        raise UI.UIError("Currently monitoring HVAC is not in the list of set HVACs")
                else:
                    #~ self.parent.parent.upper_panel.status_HVAC.SwitchOff()
                    raise UI.UIError("Currently monitoring HVAC is not in the list of set sensors")
            except KeyError:
                ShowError(self, 'Active HVAC must be chosen first')
                return -1
        elif key == 'CANCEL':
            a = self.jbox.GetValue().split(' ')[0]
            a = a.split(SettingsPanel.SEPARETOR)[1]
            job_id = int(a)
            try:
                self.remote_exec('user_interface.CLIENT.cancelJob', job_id, None, None)
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'HSET':
            hvac_id = self.rh_box.GetValue()
            if len(hvac_id) == 0:
                ShowError(self, "Register HVAC field cannot be empty.")
                return -1
            host, port = hvac_id.split(':')
            sensor_id = self.curs_box.GetValue()
            if len(sensor_id) == 0:
                ShowError(self, "Failed to set HVAC {0}. Active sensors field cannot be empty.".format(hvac_id))
                return -1
            try:
                self.remote_exec('user_interface.CLIENT.set_hvac', str(host), int(port), str(sensor_id))
                ShowInfo(self, "HVAC {0} was successfully set. Associated sensor: {1}".format(hvac_id, sensor_id))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'HDEL':
            hvac_id = self.rh_box.GetValue()
            if len(hvac_id) == 0:
                ShowError(self, "Register HVAC field cannot be empty.")
                return -1
            host, port = hvac_id.split(':')
            try:
                self.remote_exec('user_interface.CLIENT.unregister_hvac', str(host), int(port))
                ShowInfo(self, "HVAC {0} was successfully unregistered(removed).")
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'SSET':
            sensor_id = self.rs_box.GetValue()
            if len(sensor_id) == 0:
                ShowError(self, "Register sensor field cannot be empty.")
                return -1
            host, port, path = sensor_id.split(':')
            print host ,port, path
            try:
                self.remote_exec('user_interface.CLIENT.set_sensor', str(host), int(port), str(path), 0, 0)
                ShowInfo(self, "Sensor {0} was successfully set.".format(sensor_id))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'SDEL':
            sensor_id = self.rs_box.GetValue()
            if len(sensor_id) == 0:
                ShowError(self, "Register sensor field cannot be empty.")
                return -1
            host, port, path = sensor_id.split(':')
            print host ,port, path
            try:
                self.remote_exec('user_interface.CLIENT.unregister_sensor', str(host), int(port), str(path))
                ShowInfo(self, "Sensor {0} was successfully set.".format(sensor_id))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'HUNSET':
            hvac_id = self.curh_box.GetValue()
            if len(hvac_id) == 0:
                ShowError(self, "Register HVAC field cannot be empty.")
                return -1
            host, port = hvac_id.split(':')
            try:
                self.remote_exec('user_interface.CLIENT.unset_hvac', str(host), int(port))
                ShowInfo(self, "HVAC {0} was successfully unset. All jobs for the current HVAC were also cancelled".format(hvac_id))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'SUNSET':
            sensor_id = self.curs_box.GetValue()
            if len(sensor_id) == 0:
                ShowError(self, "Register sensor field cannot be empty.")
                return -1
            host, port, path = sensor_id.split(':')
            try:
                self.remote_exec('user_interface.CLIENT.unset_sensor', str(host), int(port), str(path))
                ShowInfo(self, "Sensor {0} was successfully unset.".format(sensor_id))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'HNEW':
            stripped = self.new_hvac_cmd.GetValue().split(SettingsPanel.CMD_SEPARATOR)
            if len(stripped) > 2:
                ShowError(self, "Two timestamp separators {0} are used. Can only be one".format(SettingsPanel.CMD_SEPARATOR)) 
                return -1
            elif len(stripped) == 2:
                self.new_hvac_cmd.SetValue(stripped[1])
            params = self.new_hvac_cmd.GetValue().split('%')
            if params[len(params)-1] == '':
                params = params[:len(params)-1]
            if len(params) < 5:
                ShowError(self, "The first 5 parameters are requred") 
                return -1
            else:
                # Default values
                cool_wattage = 1000
                heat_wattage = 1000
                cool_kwph = 0
                heat_kwph = 0
                description = "Unnamed"
                host = str(params[0])
                try:
                    port = int(params[1])
                    if port > 65535 or port < 0:
                        ShowError(self, "Port must be numerical value: 0 - 65535")
                        return -1
                except ValueError:
                    ShowError(self, "Port must be numerical value: 0 - 65535")
                    return -1
                username = str(params[2])
                password = str(params[3])
                if len(password) == 0:
                    password = None
                path = str(params[4])
                try:
                    cool_wattage = int(params[5])
                    heat_wattage = int(params[6])
                    cool_kwph = int(params[7])
                    heat_kwph = int(params[8])
                    description = str(params[9])
                except IndexError:
                    pass
                except ValueError:
                    ShowError(self, "Secondary parameters must be as follows:\ncool_wattage - int\nheat_wattage - int\ncool_kwph - int\nheat_kwph - int")
                    return -1
        elif key == 'HHCL':
            d_from = self.from_field.GetValue()
            d_to = self.to_field.GetValue()
            # No errors handled here. Remote exception will pop up if there was an error in data format
            try:
                self.remote_exec('user_interface.CLIENT.clean_hvacs_hist', d_from, d_to)
                ShowInfo(self, "HVAC history from {0} to {1} was cleaned up".format(d_from, d_to))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'SHCL':
            d_from = self.from_field.GetValue()
            d_to = self.to_field.GetValue()
            # No errors handled here. Remote exception will pop up if there was an error in data format
            try:
                self.remote_exec('user_interface.CLIENT.clean_sensors_hist', d_from, d_to)
                ShowInfo(self, "Sensor history from {0} to {1} was cleaned up".format(d_from, d_to))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'JHCL':
            d_from = self.from_field.GetValue()
            d_to = self.to_field.GetValue()
            # No errors handled here. Remote exception will pop up if there was an error in data format
            try:
                self.remote_exec('user_interface.CLIENT.clean_jobs_hist', d_from, d_to)
                ShowInfo(self, "Job history from {0} to {1} was cleaned up".format(d_from, d_to))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        elif key == 'SNEW':
            stripped = self.new_sensor_cmd.GetValue().split(SettingsPanel.CMD_SEPARATOR)
            if len(stripped) > 2:
                ShowError(self, "Two timestamp separators {0} are used. Can only be one".format(SettingsPanel.CMD_SEPARATOR)) 
                return -1
            elif len(stripped) == 2:
                self.new_sensor_cmd.SetValue(stripped[1])
            params = self.new_sensor_cmd.GetValue().split('%')
            if params[len(params)-1] == '':
                params = params[:len(params)-1]
            if len(params) < 5:
                ShowError(self, "All the parameters are requred") 
                return -1
            else:
                host = str(params[0])
                try:
                    port = int(params[1])
                    if port > 65535 or port < 0:
                        ShowError(self, "Port must be numerical value: 0 - 65535")
                        return -1
                except ValueError:
                    ShowError(self, "Port must be numerical value: 0 - 65535")
                    return -1
                username = str(params[2])
                password = str(params[3])
                if len(password) == 0:
                    password = None
                path = str(params[4])
            stype = self.s_type_cb.GetValue()
            try:
                stype = getattr(sensor, stype)
            except AttributeError as err:
                print err
                ShowError(self, "Sensor type must be chosen.")
                return -1
            try:
                self.remote_exec('user_interface.CLIENT.register_sensor', stype, host, port, username, password, path, config.SSHRPC)
                ShowInfo(self, "HVAC {0}:{1} was successfully registered.".format(host, port))
            except UI.UIError as err:
                ShowError(self, err.msg)
                return -1
        
        # Once changes has been done refresh the layout of the settings panel
        self.Refresh()
        return 0
        
            
    def remote_exec(self, r_api, *args):
        MyFrame.GLOCK.acquire()
        res = None
        try:
            res = self.parent.parent.TI.sysint.execute(r_api, self.parent.parent.TI.auth_id, self.parent.parent.TI.username, self.parent.parent.TI.pass_hash, *args)
        except UI.UIError as err:
            ShowError(self, err.msg)
            raise UI.UIError("Remote exception occured. Operation failed", UI.UIError.REMOTE_EXCEPTION)
        except TypeError as err:
            print err
            raise err
        finally:
            MyFrame.GLOCK.release()
        return res
    # Fills out all the comboboxes on the settings panel
    def Refresh(self):
        if self.parent.parent.TI.sysint == None:
            return None
        D = {'RH':self.rh_box, 'RS':self.rs_box, 'AH':self.curh_box, 'AS':self.curs_box, 'J':self.jbox, 'HH':self.new_hvac_cmd, 'HS':self.new_sensor_cmd}
        try:
            for k,v in D.iteritems():
                v.Clear()
                if k == 'HH': 
                    v.SetValue(SettingsPanel.H_DESCRIPTION_LABEL)
                elif k == 'HS':
                    v.SetValue(SettingsPanel.S_DESCRIPTION_LABEL)
                else:
                    v.SetValue('')
        except AttributeError as err:
            raise err
        
        MyFrame.LAYOUT_EVENT_1.event().clear()
        # If the GET_ESSENTIALS job is running then wait on it
        if self.parent.parent.SC.resetWaitFor(MyFrame.GET_ESSENTIALS):
            MyFrame.LAYOUT_EVENT_1.event().wait()
        # Otherwise, there was a problem that caused GET_ESSENTIALS to be cancelled
        else:
            return None
        
        if self.parent.parent.TI.nm_hvac != None:
            self.nm_indicator.setText(self.parent.parent.TI.nm_hvac.hvac_id)
        else:
            self.nm_indicator.setText('None')
        try:
            L = []
            for k,v in self.parent.parent.TI.jobs.iteritems():
                L.append("JOB_ID{2}{0} TYPE{2}{1}".format(str(getattr(v, v.key)), v.job_type, SettingsPanel.SEPARETOR))
            D['J' ].AppendItems(L)
            L = []
            for k,v in self.parent.parent.TI.hvacs.iteritems():
                L.append(str(getattr(v, v.key)))
            D['RH'].AppendItems(L)
            L = []
            for k,v in self.parent.parent.TI.sensors.iteritems():
                L.append(str(getattr(v, v.key)))
            D['RS'].AppendItems(L)
            L = []
            for k,v in self.parent.parent.TI.cur_hvacs.iteritems():
                L.append(str(getattr(v, v.key)))
            D['AH'].AppendItems(L)
            L = []
            for k,v in self.parent.parent.TI.cur_sensors.iteritems():
                L.append(str(getattr(v, v.key)))
            D['AS'].AppendItems(L)
            L = []
            for k,v in self.parent.parent.TI.hist_hvacs.iteritems():
                o = unpic(v.hvac)
                #Template: 'host%port%username%password%path%cool_wattage%heat_wattage%cool_kwph%heat_kwph%description'
                cmd = "{0}{1}{2}%{3}%{4}%%{5}%{6}%{7}%{8}%{9}%{10}".format(v.timestamp, SettingsPanel.CMD_SEPARATOR, o.host, o.port, o.username, o.path, o.cool_wattage, o.heat_wattage, o.cool_kwph, o.heat_kwph, o.description)
                L.append(str(cmd))
            D['HH'].AppendItems(L)
            L = []
            for k,v in self.parent.parent.TI.hist_sensors.iteritems():
                o = unpic(v.sensor)
                #Template: 'host%port%username%password%path'
                cmd = "{0}{1}{2}%{3}%{4}%%{5}".format(v.timestamp, SettingsPanel.CMD_SEPARATOR, o.host, o.port, o.username, o.path)
                L.append(str(cmd))
            D['HS'].AppendItems(L)
        except AttributeError as err:
            print err
        except TypeError as err:
            print err
            print L
        self.Layout()
    def Show(self):
        self.Refresh()
        super(SettingsPanel, self).Show()
    def Unavailable(self):
        wx.PostEvent(self, SettingsPanel.UNAVAILABLE())
    def Available(self):
        wx.PostEvent(self, SettingsPanel.AVAILABLE())
    def onAvailabale(self, event):
        for i in self.control_list:
            i.Show()
        self.error_label.Hide()
    def onUnavailable(self, event):
        for i in self.control_list:
            i.Hide()
        self.error_label.Show()


class InfoPanel(ScrollPanel):
    
    SIZE = (MainPanel.SIZE[0], MainPanel.SIZE[1] - UpperPanel.SIZE[1] - LowerPanel.SIZE[1])
    POS = (0, UpperPanel.POS[1] + UpperPanel.SIZE[1])
    BG = None
    X_MARGIN = 15
    Y_MARGIN = 20
    FONT_SIZE = 10
    FONT_SIZE2 = 17
    FONT_COLOR = (0,0,0)
    ERR_FONT_SIZE = 14
    ERR_FONT_COLOR = (255,0,0)
    TITLE_FONT_SIZE = 20
    TITLE_FONT_COLOR = (0,0,0)
    SPACING = 10

    ''' Attributes for the panel'''
    TITLE = 'INFORMATION'
    ERROR = 'Error: connection to the system has not been done'
    
    FBOX_SIZE = (len(TITLE)*TITLE_FONT_SIZE-20, 220)
    DBOX_SIZE = (MainPanel.SIZE[0] - FBOX_SIZE[1] - 2*X_MARGIN - 10, 220)
    
    FBOX_LABEL = 'Choose data type to view the information about:'
    
    AVAILABLE,  EVT_AVAILABLE  = newevent.NewEvent()
    UNAVAILABLE, EVT_UNAVAILABLE = newevent.NewEvent()
    
    COMBOBOX_W = (100,30)
    DEV_CHOICES = {'Heater':0, "A/C":1}
    
    def __init__(self, frame):
        self.parent = frame
        super(InfoPanel, self).__init__(self.parent, -1, size=InfoPanel.SIZE, pos=InfoPanel.POS, bg_rpath=InfoPanel.BG)
        
        self.FBOX_MAP = {'Users':('user_interface.CLIENT.read_users', None),
                'Logged users':('user_interface.CLIENT.read_current_clients', None),
                'HVACs':('user_interface.CLIENT.read_hvacs', None),
                'Current HVACs':('user_interface.CLIENT.read_current_hvacs', None),
                'Sensors':('user_interface.CLIENT.read_sensors', None),
                'Current sensors':('user_interface.CLIENT.read_current_sensors', None),
                'Login history':('user_interface.CLIENT.read_history_clients', None),
                'HVACs history':('user_interface.CLIENT.read_history_hvacs', None),
                'Sensor history':('user_interface.CLIENT.read_history_sensors', None),
                'Jobs':('user_interface.CLIENT.read_jobs', None),
                'Job history':('user_interface.CLIENT.read_history_hvac_job', None) }
                
        spacing = InfoPanel.SPACING
        xpos = ypos = 0 
        Font = wx.Font(InfoPanel.FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        Font2 = wx.Font(InfoPanel.FONT_SIZE2, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        ErrFont = wx.Font(InfoPanel.ERR_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        TitleFont = wx.Font(InfoPanel.TITLE_FONT_SIZE, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        
        # Dummy objects used to create sizer. Make changes at this time when everything works fine is not fasible. Therefore I will do it this way
        dummy = wx.StaticText(self, -1, " ", pos=(0,0))
        
        # Title
        self.title = wx.StaticText(self, -1, InfoPanel.TITLE, pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos))
        self.title.SetForegroundColour(InfoPanel.TITLE_FONT_COLOR)
        self.title.SetFont(TitleFont)
        ypos += 4 * spacing
        ypos += 1 * spacing
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.title, 0, wx.LEFT, InfoPanel.X_MARGIN)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(hSizer, 0, wx.TOP, InfoPanel.Y_MARGIN)
        
        # Error label
        self.error_label = wx.StaticText(self, -1, InfoPanel.ERROR, pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos))
        self.error_label.SetForegroundColour(InfoPanel.ERR_FONT_COLOR)
        self.error_label.SetFont(ErrFont)
        xpos = 0
        
        # Bind panel availability events
        self.Bind(InfoPanel.EVT_AVAILABLE, self.onAvailabale)
        self.Bind(InfoPanel.EVT_UNAVAILABLE, self.onUnavailable)
        
        # Creating an additional panel
        self.cpanel = wx.Panel(self, -1, pos=(0, ypos), size=(config.MAIN_X, 250))
        
        # Adding Year/Month combo boxes and labels
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.y_cmlab = wx.StaticText(self.cpanel, -1, 'Year:', pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos))
        self.y_cmlab.SetFont(Font2)
        hSizer.Add(self.y_cmlab, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        self.y_cmbox = wx.ComboBox(self.cpanel, -1, 'Year' , (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), InfoPanel.COMBOBOX_W, [])
        hSizer.Add(self.y_cmbox, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        self.m_cmlab = wx.StaticText(self.cpanel, -1, 'Month:', pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos))
        self.m_cmlab.SetFont(Font2)
        hSizer.Add(self.m_cmlab, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        self.m_cmbox = wx.ComboBox(self.cpanel, -1, 'Month', (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), InfoPanel.COMBOBOX_W, [])
        hSizer.Add(self.m_cmbox, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        self.dev_cmlab = wx.StaticText(self.cpanel, -1, 'Mode:', pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos))
        self.dev_cmlab.SetFont(Font2)
        hSizer.Add(self.dev_cmlab, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        self.dev_cmbox = wx.ComboBox(self.cpanel, -1, random.choice(InfoPanel.DEV_CHOICES.keys()), (SettingsPanel.X_MARGIN + xpos, SettingsPanel.Y_MARGIN + ypos), InfoPanel.COMBOBOX_W, InfoPanel.DEV_CHOICES.keys())
        hSizer.Add(self.dev_cmbox, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        self.upper_pane = hSizer
        
        # Bind events on combo boxes
        self.y_cmbox.Bind(wx.EVT_COMBOBOX, self.populateMonths)
        self.m_cmbox.Bind(wx.EVT_COMBOBOX, self.redraw)
        self.dev_cmbox.Bind(wx.EVT_COMBOBOX, self.redraw)
        
        # Adding  a plot
        self.canvas = PlotCanvas(self.cpanel)
        toggleGrid = wx.CheckBox(self.cpanel, label="Show Grid")
        toggleGrid.Bind(wx.EVT_CHECKBOX, self.onToggleGrid)
        toggleLegend = wx.CheckBox(self.cpanel, label="Show Legend")
        toggleLegend.Bind(wx.EVT_CHECKBOX, self.onToggleLegend)
        vvSizer = wx.BoxSizer(wx.VERTICAL)
        hSizer.Add(toggleGrid, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        hSizer.Add(toggleLegend, 0, wx.LEFT | wx.BOTTOM, InfoPanel.X_MARGIN)
        vvSizer.Add(hSizer)
        vvSizer.Add(self.canvas, 1, wx.EXPAND)
        self.cpanel.SetSizer(vvSizer)
        ypos += 300
        
        # Labels
        self.fbox_label = wx.StaticText(self, -1, InfoPanel.FBOX_LABEL, pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos))
        self.fbox_label.SetForegroundColour(InfoPanel.FONT_COLOR)
        self.fbox_label.SetFont(Font)
        ypos += 2 * spacing
        
        # Function list
        self.fbox = wx.ListBox(self, -1, (InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos), InfoPanel.FBOX_SIZE, self.FBOX_MAP.keys())
        self.fbox.Bind(wx.EVT_LISTBOX, self.onClick)
        xpos += InfoPanel.FBOX_SIZE[0] + InfoPanel.SPACING
        
        # Data list
        self.dbox = wx.TextCtrl(self, pos=(InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos), size=InfoPanel.DBOX_SIZE, style=wx.TE_MULTILINE)
        self.dbox.SetEditable(False)
        #~ self.dbox = wx.ListBox(self, -1, (InfoPanel.X_MARGIN + xpos, InfoPanel.Y_MARGIN + ypos), InfoPanel.DBOX_SIZE, [])
        
        # Adding the lowest element
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(dummy, 0, wx.LEFT, SettingsPanel.X_MARGIN)
        vSizer.Add(hSizer, 0, wx.TOP, ypos+400)
        # Setting up the sizer
        self.SetSizer(vSizer)
        
        self.Unavailable()
        self.stat_d = OrderedDict()
    def populateMonths(self, event):
        year_d = self.stat_d[str(self.y_cmbox.GetValue())]
        self.m_cmbox.Clear()
        self.m_cmbox.AppendItems(year_d.keys())
        self.canvas.Draw(self.drawBarGraph(annual=True))
    def Refresh(self):
        MMAP = {1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}
        # On refresh populate the comboboxes.
        if self.parent.parent.TI.nm_hvac != None:
            self.stat_d = OrderedDict()
            hvac = self.parent.parent.TI.hvacs[self.parent.parent.TI.nm_hvac.hvac_id]
            hu = unpic(hvac.heat_usage)
            cu = unpic(hvac.cool_usage)
            hkeys = hu.keys()
            epoch = {}
            for i in hkeys:
                epoch[ int(time.mktime(time.strptime(i, config.USAGE_TIME_FMT))) ] = i
            epoch_keys = epoch.keys()
            epoch_keys.sort()
            self.stat_d = OrderedDict()
            # Pre-allocate a dictionary
            s = timestamp(fmt='%Y', t=epoch_keys[0])
            e = timestamp(fmt='%Y', t=epoch_keys[len(epoch_keys)-1])
            for i in range(int(s),int(e)+1,1):
                self.stat_d[str(i)] = OrderedDict()
            # Pre-allocate months
            for i in epoch_keys:
                y = timestamp(fmt='%Y', t=i)
                m = MMAP[int(timestamp(fmt='%Y-%m', t=i).split('-')[1])]
                d = int(timestamp(fmt='%Y-%m-%d', t=i).split('-')[2])
                if not m in self.stat_d[y]:
                    self.stat_d[y][m] = OrderedDict()
                self.stat_d[y][m][d] = ((round(hu[epoch[i]],2), round(cu[epoch[i]],2)))
            self.y_cmbox.Clear()
            self.y_cmbox.AppendItems(self.stat_d.keys())
    def Show(self):
        self.Refresh()
        super(InfoPanel, self).Show()
    def redraw(self, event):
        self.canvas.Draw(self.drawBarGraph())
    def drawBarGraph(self, event=None, annual=False):
        MMAP = {1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}
        self.canvas.Clear()
        if self.parent.parent.TI.nm_hvac == None or not str(self.dev_cmbox.GetValue()) in InfoPanel.DEV_CHOICES:
            dummy_p = [(0,0), (0,0)]
            dummy_l = PolyLine(dummy_p)
            return PlotGraphics([dummy_l], "Device Usage - (Turn on Grid, Legend)", "Time", "Hours worked")
        hvac = self.parent.parent.TI.hvacs[self.parent.parent.TI.nm_hvac.hvac_id]
        # 1. fetch parameters from the year and month comboboxes.
        y = str(self.y_cmbox.GetValue())
        m = str(self.m_cmbox.GetValue())
        try:
            d = self.stat_d[str(y)]
        except KeyError:
            dummy_p = [(0,0), (0,0)]
            dummy_l = PolyLine(dummy_p)
            return PlotGraphics([dummy_l], "Device Usage - (Turn on Grid, Legend)", "Time", "Hours worked")
        # Preallocate point and line lists
        P = {}
        L = []
        WIDTH = 10
        if annual:
            acc = OrderedDict()
            # Iterate through the year
            for k,v in d.iteritems():
                # Iterate through each month
                acc[k] = [0,0]
                for K,V in v.iteritems():
                    acc[k][0] += V[0]
                    acc[k][1] += V[1]
                acc[k][0] = round(acc[k][0], 2)
                acc[k][1] = round(acc[k][1], 2)
            for idx in range(1,13,1):
                try:
                    hp = (idx, acc[MMAP[idx]][0])
                    cp = (idx, acc[MMAP[idx]][1])
                    P[idx] = ( [(idx,0), hp], [(idx,0), cp] )
                except KeyError as ex:
                    P[idx] = ( [(0,0), (0,0.00001)], [(0,0), (0,0.00001)] )
            for k,v in P.iteritems():
                if v == None:
                    continue
                lh = PolyLine(v[0], colour='red', legend='Heat', width=WIDTH)
                lc = PolyLine(v[1], colour='blue', legend='Cool', width=WIDTH)
                if InfoPanel.DEV_CHOICES[str(self.dev_cmbox.GetValue())] == 0:
                    L.append(lh)
                else:
                    L.append(lc)
            return PlotGraphics(L,"Annual Device Usage - (Turn on Grid, Legend)", 'Months in {0}'.format(y), "Hours worked")
        else:
            try:
                month = d[m]
            except KeyError:
                dummy_p = [(0,0), (0,0)]
                dummy_l = PolyLine(dummy_p)
                return PlotGraphics([dummy_l], "Device Usage - (Turn on Grid, Legend)", "Time", "Hours worked")
            for idx in range(1, 32, 1):
                try:
                    hp = (idx,month[idx][0])
                    cp = (idx,month[idx][1])
                    P[idx] = ( [(idx,0), hp], [(idx,0), cp] )
                except KeyError as ex:
                    P[idx] = ( [(0,0), (0,0.00001)], [(0,0), (0,0.00001)] )
            for k,v in P.iteritems():
                if v == None:
                    continue
                lh = PolyLine(v[0], colour='red', legend='Heat', width=WIDTH)
                lc = PolyLine(v[1], colour='blue', legend='Cool', width=WIDTH)
                if InfoPanel.DEV_CHOICES[str(self.dev_cmbox.GetValue())] == 0:
                    L.append(lh)
                else:
                    L.append(lc)
            return PlotGraphics(L,"Monthly Device Usage - (Turn on Grid, Legend)", 'Days in {0}'.format(m), "Hours worked")
        # In case somthing gets fucked up this is a resue way in order not to crash
        dummy_p = [(0,0), (0,0)]
        dummy_l = PolyLine(dummy_p)
        return PlotGraphics([dummy_l], "Device Usage - (Turn on Grid, Legend)", "Time", "Hours worked")
    
    def onToggleGrid(self, event):
        self.canvas.SetEnableGrid(event.IsChecked())
    def onToggleLegend(self, event):
        self.canvas.SetEnableLegend(event.IsChecked())
    def onClick(self, event):
        self.dbox.Clear()
        r_api = self.FBOX_MAP[self.fbox.GetStringSelection()][0]
        render_f = self.FBOX_MAP[self.fbox.GetStringSelection()][1]
        if render_f == None:
            render_f = ics_types.toString
        # Trying to retrieve data
        MyFrame.GLOCK.acquire()
        try:
            res = self.parent.parent.TI.sysint.execute(r_api, self.parent.parent.TI.auth_id, self.parent.parent.TI.username, self.parent.parent.TI.pass_hash)
            for k,v in res.iteritems():
                self.dbox.AppendText(render_f(v))
        except UI.UIError as err:
            print err
            self.Unavailable()
        except TypeError as err:
            print err
            self.Unavailable()
        finally:
            MyFrame.GLOCK.release()
    def Unavailable(self):
        wx.PostEvent(self, InfoPanel.UNAVAILABLE())
    def Available(self):
        wx.PostEvent(self, InfoPanel.AVAILABLE())
    def onAvailabale(self, event):
        self.error_label.Hide()
        self.fbox.Show()
        self.dbox.Show()
        self.cpanel.Show()
        self.fbox_label.Show()
    def onUnavailable(self, event):
        self.error_label.Show()
        self.fbox.Hide()
        self.dbox.Hide()
        self.cpanel.Hide()
        self.fbox_label.Hide()
class MyFrame(wx.Frame):
    
    # TASK_LIST
    GET_ESSENTIALS = 'GET_ESSENTIALS'
    GLOCK = Lock()
    
    # Frame position
    #~ pX = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)
    #~ pY = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)
    POS = (0,0)
    
    # Define global layout conditional variable and clear it
    LAYOUT_EVENT_1 = atomic.AtomicUnit(0, True)
    
    def __del__(self):
        self.SC.stop()
        super(MyFrame, self).__del__()
    def __init__(self, parent):

        self.TI = UI.ThermostatInterface()
        self.SC = UI.Scheduler()

        wx.Frame.__init__(self, parent, -1, "Thermostat Panel", size=MainPanel.SIZE, style=wx.DEFAULT_FRAME_STYLE ^ (wx.RESIZE_BORDER), pos=MyFrame.POS)
        '''wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN'''

        '''Setting up the main panel'''
        self.main_panel = MainPanel(self)
        
        '''Setting up the login panel'''
        self.connection_panel = ConnectionPanel(self.main_panel)
        self.connection_panel.setControlObject(self.TI)
        self.connection_panel._populateFields()
        self.connection_panel.Hide()
        
        '''Setting uo the settings panel'''
        self.settings_panel = SettingsPanel(self.main_panel)
        self.settings_panel.Hide()
        
        '''Setting up info panel'''
        self.info_panel = InfoPanel(self.main_panel)
        self.info_panel.Hide()
        
        '''Setting up the upper panel'''
        self.upper_panel = UpperPanel(self.main_panel)
        
        '''Setting up the lower panel'''
        self.lower_panel = LowerPanel(self.main_panel)
        
        self.task_list = None
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.SC.start()

    def OnErase(self, evt):
        # To reduce flicker
        pass
    
    def OnClose(self, evt):
        MyFrame.GLOCK.acquire()
        self.Destroy()
        MyFrame.GLOCK.release()

    def OnSize(self, evt):
        #Avoid Flickering
        self.Freeze()
        
        self.Thaw()


def run():
    app = wx.App(0)

    frame = MyFrame(None)
    app.SetTopWindow(frame)
    frame.Show()
    t = Thread(target=app.MainLoop)
    t.start()
    t.join()

# our normal wxApp-derived class, as usual
if __name__ == '__main__':
    make_pics()
    run()
