#!/usr/bin/python3

#TODO: Add GIT refresh buttons

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject, GLib
import math
import sys
import os
sys.path.append("./G2D")
import platform
import git
import time
from tendo import singleton

try:
    me = singleton.SingleInstance()
except:
    sys.exit(0)



#host_env is temp right now until we determine how to know what evn we are in
if platform.processor() == "x86_64":
    sys.path.append("./G2D/x86")
    host_env = "PARALLELS"
else:
    sys.path.append("./G2D/arm")
    host_env = "PI"
import G2Dhost
import cairo
import subprocess
from threading  import Thread
import glob

version = 1.0        

#                C     C#    D     D#    E     F     F#    G     G#    A     A#     B      C      C#      D
GetMIDINote = { 'A':0,'W':1,'S':2,'E':3,'D':4,'F':5,'T':6,'G':7,'Y':8,'H':9,'U':10,'J':11,'K':12,'O':13,'L':14 }

log_i = 1

class Screen(Gtk.DrawingArea):
    """ This class is a Drawing Area"""
    def __init__(self):
        super(Screen,self).__init__()
        G2Dhost.Setup()
        self.surface = cairo.ImageSurface.create_for_data(G2Dhost.GetImgPtr(),cairo.FORMAT_ARGB32,320,240);
        ## Connect to the "draw" signal
        self.connect("draw", self.on_draw)
        ## This is what gives the animation life!
        GLib.timeout_add(10, self.tick) # Go call tick every 10 whatsits.

    def tick(self):
        rect = Gdk.Rectangle();
        rect.width = 320
        rect.height = 240
        self.get_window().invalidate_rect(rect, True)
        return True # Causes timeout to tick again.

    ## When the "draw" event fires, this is run
    def on_draw(self, widget, event):
        self.cr = self.get_window().cairo_create()
        self.draw(self.cr)

    def draw(s,cr):
        if G2Dhost.CheckRestart():
            s.p.startProcess()
        #Handle time
        #s.p.controls[f"f{n}_s"].get_value()
        if s.p.timeActive.get_active():
            new_time = float(s.p.itime) + s.p.ftime + 0.5*0.01*s.p.timeSlider.get_value()
        else:
            new_time = float(s.p.itime) + s.p.ftime + 0.5*0.01
        s.p.itime = int(new_time)
        s.p.ftime = new_time%1.0
        G2Dhost.SetTime(s.p.itime,s.p.ftime)

        G2Dhost.ProcessModulations(*[s.p.StructUI[k].get_active() for k in ["cEMT","cRM","cRNRW","cRVR","cRL","cFM"]])

        #Check for new names
        if G2Dhost.CheckNewFPN:
            for i in range(3):
                n = G2Dhost.GetFPN(i)
                if n == "":
                    s.p.controls[f"f{i}_l"].set_text("<no label>")
                else:    
                    s.p.controls[f"f{i}_l"].set_text(n)

        #Go through and determine what mode we are in, use accumulators for LFO mode
        for n in [0,1,2]:
            if s.p.controls[f"f{n}_r"].get_active():
                G2Dhost.SetFParam(n,(1.0+math.sin(s.p.controls[f"f{n}_a"]))/2.0)
                # 0 to 1
                delta = s.p.controls[f"f{n}_s"].get_value()
                # map to 0.05 to 1
                delta = (delta*0.95) + 0.05

                s.p.controls[f"f{n}_a"] = s.p.controls[f"f{n}_a"]+delta

            else:
                G2Dhost.SetFParam(n,s.p.controls[f"f{n}_s"].get_value())

        G2Dhost.WaitHostAccess()
        G2Dhost.ProcessFrame()
        cr.set_source_surface(s.surface,0,0)
        cr.paint()
        G2Dhost.GiveHostAccess()


class MyWindow(Gtk.Window):

    def __init__(s):
        super(MyWindow, s).__init__()
        s.outp = None
        s.t    = None
        
        if host_env == "PARALLELS":
            s.f2dpy_path = "/media/user/STRUCT_SD"
        else:
            s.f2dpy_path = "/media/pi/STRUCT_SD"


        style_provider = Gtk.CssProvider()
        css = open('s2d.css','rb')
        css_data = css.read()
        css.close()
        style_provider.load_from_data(css_data)
        Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                style_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        s.set_title(f"STRUCTURE 2D Program Viewer {version}")
        s.resize(800, 800)
        s.connect("destroy", Gtk.main_quit)
        s.midiOffset = 3*12 
        s.velocity = 127

        s.grid = Gtk.Grid()
        s.add(s.grid)

        #s.bReload = Gtk.Button(label="Reload")
        #s.bReload.connect("clicked",s.bReloadClicked)
        #s.grid.attach(s.bReload,0,0,2,1)

        #s.bReload = Gtk.Button(label="Save State")
        #s.bReload.connect("clicked",s.bReloadClicked)
        #s.grid.attach(s.bReload,2,0,2,1)

        #s.bReload = Gtk.Button(label="Reset State")
        #s.bReload.connect("clicked",s.bReloadClicked)
        #s.grid.attach(s.bReload,4,0,2,1)

        s.controls = {}

        s.lFp = Gtk.Label()
        s.lFp.set_markup("<b>F Parameters</b>")
        s.grid.attach(s.lFp,0,1,1,1)
        s.lFm = Gtk.Label()
        s.lFm.set_markup("<b>Mode</b>")
        s.grid.attach(s.lFm,1,1,1,1)

        i=2
        for n in ["f0","f1","f2"]:
            s.controls[n+"_l"] = Gtk.Label()
            s.controls[n+"_l"].set_text("<no label>")
            s.grid.attach(s.controls[n+"_l"],0,i,1,1)
            i = i+1

            s.controls[n+"_s"] = Gtk.Scale()
            s.controls[n+"_s"].set_range(0,1)
            s.controls[n+"_s"].set_digits(2)
            s.controls[n+"_s"].set_value(0.5)
            s.controls[n+"_s"].set_size_request(120,20)
            s.grid.attach(s.controls[n+"_s"],0,i,1,1)

            s.controls[n+"_r"] = Gtk.CheckButton(label="LFO")
            s.controls[n+"_r"].set_active(False)
            #s.controls[n+"_r"].set_valign(Gtk.Align.START)
            #s.controls[n+"_r"].connect("clicked", s.on_click)
            s.grid.attach(s.controls[n+"_r"],1,i,1,1)
    
            s.controls[n+"_a"] = 0.0

            i = i+1
        
        s.bAcc = Gtk.Button(label="Accent")
        s.bAcc.connect("clicked",s.bAccClicked)
        s.bAcc.get_style_context().add_class("color_red")
        s.bAccState = 0
        s.grid.attach(s.bAcc,0,i,2,1)
        i = i+1

        s.bTrig = Gtk.Button(label="Trigger")
        s.bTrig.connect("clicked",s.bTrigClicked)
        s.grid.attach(s.bTrig,0,i,2,1)
        i = i+1

        s.dArea = Screen()
        s.dArea.p = s
        s.dArea.set_size_request(320,240)
        s.grid.attach(s.dArea,2,1,1,16)
        s.ftime = 0.0
        s.itime = 0

        #Mimic Structure UI Settings here
        i = 1

        s.StructUI = {}

        data = [
                [ "cEMT","Extra Mod Type", ["Rand","MIDI","Freq"] ],
                [ "cRM", "Rand Mode", ["Note","Value"] ],
                [ "cRNRW", "Rand Note Rate Wait", ["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20"] ],
                [ "cRVR", "Rand Velocity Rand", ["0","1","2","3","4","5","6","7","8","9","10"] ],
                [ "cRL", "Rand Length", ["1","2","3","4","5","6","7","8","9","10"] ],
                [ "cFM", "Freq Mode", ["Fast","Decay"] ]
            ]
        for r in data:
            (name,desc,options) = r
            s.grid.attach(Gtk.Label(label=desc),3,i,1,1)
            s.StructUI[name] = Gtk.ComboBoxText()
            s.StructUI[name].set_entry_text_column(0)
            #s.StructUI[name].connect("changed",s.StructUI[name].callback)
            for n in options:
                s.StructUI[name].append_text(n)
            s.StructUI[name].set_active(0)
            s.grid.attach(s.StructUI[name],4,i,1,1)
            i = i+1

        #The only callback we need from above is changing cEMT or cRM
        s.StructUI["cEMT"].connect("changed",s.ModeChanged)
        s.StructUI["cRM"].connect("changed",s.ModeChanged)

        # Add Time Control [slider, active value]
        s.timeLab = Gtk.Label(label="Adj Time Control")
        s.grid.attach(s.timeLab,3,i,1,1)
        s.timeLab.set_sensitive(False)

        s.timeSlider = Gtk.Scale()
        s.timeSlider.set_range(-2,2)
        s.timeSlider.set_digits(2)
        s.timeSlider.set_value(0.0)
        s.timeSlider.set_size_request(120,20)
        s.timeSlider.set_sensitive(False)
        s.grid.attach(s.timeSlider,4,i,1,1)
        i = i+1

        s.timeActive = Gtk.CheckButton(label="Active")
        s.timeActive.set_active(False)
        s.grid.attach(s.timeActive,4,i,1,1)
        s.timeActive.connect("toggled",s.TimeActiveChanged)

        # TODO: Add visualizer for different modes

        s.midib = {}
        fixed = Gtk.Fixed()
        s.grid.attach(fixed,0,17,3,1)
        offset = 25
        for i in ["W","E","","T","Y","U","","O"]:
            if i != "":
                s.midib[i] = Gtk.Button(label=i)
                s.midib[i].get_style_context().add_class("midi_black_up")
                s.midib[i].upstyle = "midi_black_up"
                s.midib[i].set_size_request(50,50)
                s.midib[i].connect("pressed",s.bMIDIPressed)
                s.midib[i].connect("released",s.bMIDIReleased)
                fixed.put(s.midib[i],offset,0)
            offset = offset + 50

        offset = 0
        for i in ["A","S","D","F","G","H","J","K","L"]:
            s.midib[i] = Gtk.Button(label=i)
            s.midib[i].get_style_context().add_class("midi_white_up")
            s.midib[i].upstyle = "midi_white_up"
            s.midib[i].set_size_request(50,50)
            s.midib[i].connect("pressed",s.bMIDIPressed)
            s.midib[i].connect("released",s.bMIDIReleased)
            fixed.put(s.midib[i],offset,50)
            
            offset = offset + 50

        offset = 25
        for i in ["Z","X"]:
            s.midib[i] = Gtk.Button(label=i)
            s.midib[i].get_style_context().add_class("midi_octave_up")
            s.midib[i].set_size_request(50,50)
            s.midib[i].connect("pressed",s.bMIDIPressed)
            s.midib[i].connect("released",s.bMIDIReleased)
            fixed.put(s.midib[i],offset,100)
            offset = offset + 50

        s.connect("key-press-event",s.key_press_event)
        s.connect("key-release-event",s.key_release_event)

        s.keyTrack = {}

        s.octave = Gtk.Label(label=f"Octave: {s.midiOffset//12}")
        fixed.put(s.octave,150,115)


        #initialize all the structure UI callbacks

        s.SendStructureUISettings()

        bts = Gtk.VBox()
        s.bUpdate = Gtk.Button(label="Check For Updates")
        s.bUpdate.connect("clicked",s.bCheckForUpdates)
        bts.add(s.bUpdate)

        s.bAutoS = Gtk.CheckButton()
        s.bAutoS.set_label("Autoscroll")
        s.autoscroll = True
        s.bAutoS.connect("toggled",s.toggle_autos)
        s.bAutoS.set_active(True)
        bts.add(s.bAutoS)

        s.bIgn = Gtk.CheckButton()
        s.bIgn.set_label("Ignore Output")
        s.ignore = False
        s.bIgn.connect("toggled",s.toggle_ignore)
        s.bIgn.set_active(False)
        bts.add(s.bIgn)

        s.bClear = Gtk.Button(label="Clear")
        s.bClear.connect("clicked",s.clearText)
        bts.add(s.bClear)

        s.grid.attach(bts,4,17,1,1)

        sw = Gtk.ScrolledWindow()
        sw.set_hexpand(True)
        sw.set_vexpand(True)
        s.grid.attach(sw,0,18,8,4)

        s.logV = Gtk.TextView()
        s.logV.set_editable(False)
        s.logV.set_cursor_visible(False)
        s.logV.set_left_margin(10)
        s.logV.set_right_margin(10)
        s.log = s.logV.get_buffer()
        s.log.insert_markup(s.log.get_end_iter(), "Welcome to the <b>STRUCTURE 2D Test Environment</b>, below will be output from python on the parsing of your program. \n\n",-1)
        sw.add(s.logV)
        
        s.log_lines = 1
        
        # File selection
        s.cardStatus = 0 #0 = empty, 1 = card there
        t = Gtk.Label(label="File List")
        t.set_size_request(180,20)
        s.grid.attach(t,6,0,2,1)
        s.fileList = Gtk.ListBox()
        s.fileList.set_sort_func(s.SortFileList)

        vbox = Gtk.VBox()
        vbox.add(s.fileList)
        scrWin = Gtk.ScrolledWindow()
        scrWin.add(vbox)
        s.grid.attach(scrWin,6,1,2,16)
        
        fbts = Gtk.VBox()

        s.fLoad = Gtk.Button(label="Load")
        s.fLoad.connect("clicked",s.loadFile)
        fbts.add(s.fLoad)
        
        s.fEdit = Gtk.Button(label="Edit")
        s.fEdit.connect("clicked",s.editFile)
        fbts.add(s.fEdit)   

        s.fNew = Gtk.Button(label="New")
        s.fNew.connect("clicked",s.copyNewFile)
        s.fNew.kind = "new"
        fbts.add(s.fNew)

        s.fCopy = Gtk.Button(label="Copy")
        s.fCopy.connect("clicked",s.copyNewFile)
        s.fCopy.kind = "copy"
        fbts.add(s.fCopy)   

        s.fRename = Gtk.Button(label="Rename")
        s.fRename.connect("clicked",s.renameFile)
        fbts.add(s.fRename)   

        s.fDelete = Gtk.Button(label="Delete")
        s.fDelete.connect("clicked",s.deleteFile)
        fbts.add(s.fDelete)   

        s.grid.attach(fbts,6,17,2,1)

        # Add internal programs (not user changable)
        s.list_insert_point = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        s.list_insert_point.ro = 1
        s.fileList.add(s.list_insert_point)
        if os.path.isdir("./2dpy"):
            for filepath in glob.iglob("./2dpy/*.2dpy"):
                filename = os.path.basename(filepath)
                label = Gtk.Label(label = "IN: "+filename,xalign=0)
                label.path = filepath
                label.ro = 1
                s.fileList.add(label)


        s.update_files()
        s.show_all()

    def SortFileList(s,a,b):
        ac = a.get_children()[0]
        bc = b.get_children()[0]
        if type(ac).__name__ != 'Separator':
            ai = ac.get_text().split(":")
        else:
            ai = "SEP"
        if type(bc).__name__ != 'Separator':
            bi = bc.get_text().split(":")
        else:
            bi = "SEP"

        if ai == "SEP":
            if bi[0]=="SD":
                return 1
            else:
                return 0
        if bi == "SEP":
            if ai[0]=="SD":
                return 0
            else:
                return 1

        if(ai[0]=="SD" and bi[0]=="IN"):
            return 0
        elif(ai[0]=="IN" and bi[0]=="SD"):
            return 1
        else:
            return(cmp(ai[1],bi[1]))
        return 0

    def TimeActiveChanged(s,c):
        if c.get_active():
            s.timeLab.set_sensitive(True)
            s.timeSlider.set_sensitive(True)
        else:
            s.timeLab.set_sensitive(False)
            s.timeSlider.set_sensitive(False)


    def ModeChanged(s,e):
        G2Dhost.SetExtraModType(*[s.StructUI[k].get_active() for k in ["cEMT","cRM","cRNRW","cRVR","cRL","cFM"]])

    # File access might depend on installation
    def update_files(s):
        # Check if card exists, if not mark missing
        if s.cardStatus == 0:
            if os.path.isdir(s.f2dpy_path + "/2dpy"):
                #print("Files Found!!")
                s.cardStatus = 1
                fs = list(glob.iglob(s.f2dpy_path + "/2dpy/*.2dpy"))
                fs.reverse()
                for filepath in fs:
                    filename = os.path.basename(filepath)
                    label = Gtk.Label(label = "SD: "+filename,xalign=0)
                    label.path = filepath
                    label.ro   = 0
                    #s.fileList.add(label)
                    s.fileList.prepend(label)
            s.fileList.show_all()
        elif s.cardStatus == 1:
            if not os.path.isdir(s.f2dpy_path+"/2dpy"):
                #print("Files gone!!")
                for child in s.fileList.get_children():
                    if child.get_children()[0].ro == 0:
                        s.fileList.remove(child)
                s.cardStatus = 0
        GLib.timeout_add_seconds(2,s.update_files)
    def deleteFile(s,b):
        if s.fileList.get_selected_row():
            for sel in s.fileList.get_selected_row():
                if sel.ro == 1:
                    s.ShowMessage("Warning","You cannot remove an internal 2dpy program")
                else:
                    msg = Gtk.Label(label=f"Are you sure you want to delete?    {sel.get_text()}")
                    msg_dialog = Gtk.Dialog(
                        "Warning",
                        s,
                        None,
                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_OK, Gtk.ResponseType.OK)
                        )
                    msg_dialog.vbox.add(msg)
                    msg.show()
                    response = msg_dialog.run()
                    msg_dialog.destroy()
                    if response == Gtk.ResponseType.OK:
                        os.system(f"rm {sel.path}")
                        for child in s.fileList.get_children():
                            l = child.get_children()[0]
                            if l.ro == 0 and l.path == sel.path:
                                s.fileList.remove(child)

    def renameFile(s,b):
        if s.fileList.get_selected_row():
            for sel in s.fileList.get_selected_row():
                if sel.ro == 1:
                    s. ShowMessage("Warning","You cannot rename an internal 2dpy program")
                else:
                    msg = Gtk.Label(label=f"Enter a new filename (do not include .2dpy)")
                    txt = Gtk.Entry()
                    txt.set_text("new_name")
                    msg_dialog = Gtk.Dialog(
                        f"Enter new name",
                    s,
                    None,
                    (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OK, Gtk.ResponseType.OK)
                )
                msg_dialog.vbox.add(msg)
                msg_dialog.vbox.add(txt)
                msg.show()
                txt.show()
                state = 1
                while state:
                    response = msg_dialog.run()
                    if response == Gtk.ResponseType.OK:
                        #check if filename is valid and unused
                        if not s.validName(txt.get_text()):
                            s.ShowMessage("Warning","Name has invalid characters, only use a-z,0-9, and _ or - in names.")
                        elif os.path.isfile(s.f2dpy_path + "/2dpy/" + txt.get_text() + ".2dpy"):
                            s.ShowMessage("Warning","Program with this name already exists on SD card, choose another.")
                        elif ".2dpy" in txt.get_text():
                            s.ShowMessage("Warning","Do not put .2dpy in the filename.")
                        else:
                            state = 0
                            new_f = s.f2dpy_path + "/2dpy/" + txt.get_text() + ".2dpy"
                            old_f = sel.path
                            os.system(f"mv {old_f} {new_f}")
                            for child in s.fileList.get_children():
                                l = child.get_children()[0]
                                if l.ro == 0 and l.path == sel.path:
                                    s.fileList.remove(child)
                            # call update to add new entry (in case someone doing something on disk
                            filename = os.path.basename(new_f)
                            label = Gtk.Label(label = "SD: "+filename,xalign=0)
                            label.path = new_f
                            label.ro   = 0
                            s.fileList.prepend(label)
                            label.show()
                    else:
                        state = 0
                msg_dialog.destroy()



    def copyNewFile(s,b):
        #Check for a structure SD card first
        if not os.path.isdir(s.f2dpy_path):
            s.ShowMessage("Warning","No STRUCTURE card detected, cannot create new file!")
            return()
        if b.kind == "new" or len(s.fileList.get_selected_row()) > 0:
            if b.kind == "copy":
                sel = s.fileList.get_selected_row().get_children()[0]
            msg = Gtk.Label(label=f"Enter a filename for your {b.kind} (do not include .2dpy)")
            txt = Gtk.Entry()
            txt.set_text("new_name")
            msg_dialog = Gtk.Dialog(
                f"Enter Name for {b.kind}",
                s,
                None,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK, Gtk.ResponseType.OK)
            )
            msg_dialog.vbox.add(msg)
            msg_dialog.vbox.add(txt)
            msg.show()
            txt.show()
            state = 1
            while state:
                response = msg_dialog.run()
                if response == Gtk.ResponseType.OK:
                    #check if filename is valid and unused
                    if not s.validName(txt.get_text()):
                        s.ShowMessage("Warning","Name has invalid characters, only use a-z,0-9, and _ or - in names.")
                    elif os.path.isfile(s.f2dpy_path + "/2dpy/" + txt.get_text() + ".2dpy"):
                        s.ShowMessage("Warning","Program with this name already exists on SD card, choose another.")
                    elif ".2dpy" in txt.get_text():
                        s.ShowMessage("Warning","Do not put .2dpy in the filename.")
                    else:
                        state = 0
                        new_f = s.f2dpy_path + "/2dpy/" + txt.get_text() + ".2dpy"
                        if b.kind == "copy":
                                old_f = sel.path
                        else:
                            old_f = "template.template"
                        # Make sure we have the 2dpy dir
                        if not os.path.isdir(s.f2dpy_path+"/2dpy"):
                            os.system("mkdir " + s.f2dpy_path+"/2dpy")
                        os.system(f"cp {old_f} {new_f}")
                        # call update to add new entry (in case someone doing something on disk
                        filename = os.path.basename(new_f)
                        label = Gtk.Label(label = "SD: "+filename,xalign=0)
                        label.path = new_f
                        label.ro   = 0
                        s.fileList.prepend(label)
                        label.show()
                else:
                    state = 0
            msg_dialog.destroy()

    def validName(s,name):
        invalid = ["!","@","$","%","^","&","*","(",")","{","}","[","]","\"","'",":",";","<",">",",",".","?","/","|","\\","~","`"]
        for c in name:
            if c in invalid:
                return False
        return True

    def ShowMessage(s,hdr,txt):
        msg = Gtk.Label(label=txt)
        msg_dialog = Gtk.Dialog(
            hdr,
            s,
            None,
            (Gtk.STOCK_OK, Gtk.ResponseType.OK)
            )
        msg_dialog.vbox.add(msg)
        msg.show()
        response = msg_dialog.run()
        msg_dialog.destroy()


    def editFile(s,b):
        if s.fileList.get_selected_row():
            for sel in s.fileList.get_selected_row():
                if sel.ro == 1:
                    s. ShowMessage("Warning","Copy an internal 2dpy program to edit it")
                else:
                    os.system(f"gedit {sel.path}&") 

    def loadFile(s,b):
        if s.fileList.get_selected_row():
            for sel in s.fileList.get_selected_row():
                G2Dhost.LoadProgram(sel.path)

    def update_log(s,line):
        if not s.ignore:
            #s.log.insert_markup(s.log.get_end_iter(),line,-1)
            s.log.insert(s.log.get_end_iter(),line,-1)
            s.log_lines = s.log_lines + 1
            if s.log_lines < 2000:
                pass
            else:
                start = s.log.get_iter_at_line(0)
                end   = s.log.get_iter_at_line(1)
                s.log.delete(start,end)
                while Gtk.events_pending():
                    Gtk.main_iteration()
            if s.autoscroll:
                it=s.log.get_iter_at_line(s.log.get_line_count());
                s.logV.scroll_to_iter(it,0,True,0.5,0.5)
                s.logV.queue_draw()

    def SendStructureUISettings(s):

        G2Dhost.SetExtraModType(*[s.StructUI[k].get_active() for k in ["cEMT","cRM","cRNRW","cRVR","cRL","cFM"]])

    
    
    def key_press_event(s,w,e):
        if e.type == Gdk.EventType.KEY_PRESS: 
            key = Gdk.keyval_name(e.keyval).upper()
            if key in s.midib and key not in s.keyTrack: 
                s.KeyboardToMIDI(key,1)
                s.keyTrack[key]=1
            return True
    
    def key_release_event(s,w,e):
        if e.type == Gdk.EventType.KEY_RELEASE: 
            key = Gdk.keyval_name(e.keyval).upper()
            if key in s.midib:
                s.KeyboardToMIDI(key,0)
                del(s.keyTrack[key])
            return True

    def bMIDIPressed(s,w):
        s.KeyboardToMIDI(w.get_label(),1)

    def bMIDIReleased(s,w):
        s.KeyboardToMIDI(w.get_label(),0)

    def KeyboardToMIDI(s,key,status):
        #print(f"KTM: {key} {status}")
        if key != "Z" and key != "X":
            if status == 1:
                s.midib[key].get_style_context().remove_class(s.midib[key].upstyle)
                s.midib[key].get_style_context().add_class("midi_down")
            else:
                s.midib[key].get_style_context().remove_class("midi_down")
                s.midib[key].get_style_context().add_class(s.midib[key].upstyle)
            G2Dhost.SendMIDI(s.midiOffset + GetMIDINote[key], s.velocity, status)
        elif key == "Z" and status == 1:
            if s.midiOffset != 0:
                s.midiOffset = s.midiOffset-12
                s.octave.set_text(f"Octave: {s.midiOffset//12}")
        elif key == "X" and status == 1:
            if s.midiOffset != 120:
                s.midiOffset = s.midiOffset+12
                s.octave.set_text(f"Octave: {s.midiOffset//12}")

    def bCheckForUpdates(s,b):
        d = Gtk.Dialog()
        d.set_title("Update System")
        d.set_transient_for(s)
        d.set_modal(True)
        s.b1=d.add_button(button_text="Update Programs",response_id=1)
        s.b2=d.add_button(button_text="Update Editor",response_id=2)
        s.b3=d.add_button(button_text="Update Both",response_id=3)
        s.b4=d.add_button(button_text="Cancel",response_id=0)
        d.connect("response",s.bCFUResponse)
        c = d.get_content_area()
        l = Gtk.Label(label="Select which you'd like to look for updates")
        s.m1 = l
        c.add(l)
        l = Gtk.Label(label="")
        c.add(l)
        l = Gtk.Label()
        l.set_markup("<b>Note: Your networking must be working to use this feature</b>")
        s.m2 = l
        c.add(l)

        d.show_all()

    def bCFUResponse(s,w,r_id):
        if r_id == 0:
            w.destroy()
            return
        r = ""
        s.m1.set_text("Please wait while we check for updates...")
        s.m2.set_text("")
        s.b1.set_sensitive(False)
        s.b2.set_sensitive(False)
        s.b3.set_sensitive(False)
        s.b4.set_sensitive(False)
        while Gtk.events_pending():
            Gtk.main_iteration()
        if s.Ping("github.com"):
            if r_id == 2 or r_id == 3:
                r=r+s.GitUpdate(".","Editor","main")
            if r_id == 1 or r_id == 3:
                r=r+s.GitUpdate("../2dpy/.","Programs","master")
            w.destroy()
            s.ShowMessage("Result",r)
        else:
            w.destroy()
            s.ShowMessage("Error","Cannot connect to server, network not connected or host down.")
            return

    def GitUpdate(s,d,desc,b):
        print(f"Checking status of git repo in '{d}'") 
        repo = git.Repo(d)
        print(f"Fetching latest from server")
        repo.remotes.origin.fetch()
        commits_ahead  = list(repo.iter_commits(f"{b}..origin/{b}"))
        commits_behind = list(repo.iter_commits(f"origin/{b}..{b}"))

        count_a = len(commits_ahead) #newer commits on server
        count_b = len(commits_behind) #local changes that need to be erased first maybe
        if(count_a == 0):
            return(f"{desc} is already latest.\n")
        elif(count_b != 0):
            return(f"{desc} has some local changes, must be manually reset.\n")
        else:
            repo.remotes.origin.pull()
            return(f"{desc} has been updated to a newer version, please restart app.\n")
        return("")
    
    def Ping(s,h):
        print(f"Checking for '{h}' connectivity.")
        response = os.system("ping -c 1 " + h)
        if response == 0:
            return 1
        else:
            return 0

    def bReloadClicked(s,d):
        G2Dhost.LoadProgram(sys.argv[1])
        s.clearText(0)

    def clearText(s,d):
        s.log.set_text("")
        s.log_lines=1

    def bAccClicked(s,d):
        if s.bAccState == 0:
            s.bAccState = 1
            s.bAcc.get_style_context().remove_class("color_red")
            s.bAcc.get_style_context().add_class("color_green")
        else:
            s.bAccState = 0
            s.bAcc.get_style_context().remove_class("color_green")
            s.bAcc.get_style_context().add_class("color_red")
        G2Dhost.SetAccent(s.bAccState)

    def bTrigClicked(s,d):
        G2Dhost.SetTrigger()

    def toggle_autos(s,b):
        if b.get_active():
            s.autoscroll = True
        else:
            s.autoscroll = False
    def toggle_ignore(s,b):
        if b.get_active():
            s.ignore = True
        else:
            s.ignore = False

    def startProcess(s):
        if s.outp != None:
            s.outp.terminate()
        s.outp = subprocess.Popen(["python3","-u","G2D/G2D-base.py"],shell=False,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        s.t = Thread(target=enqueue_output, args=(s.outp.stdout,s,s.outp))
        s.t.daemon = True
        s.t.start()

def cmp(a,b):
    return (a>b) - (a<b)

win = MyWindow()

#G2Dhost.LoadProgram(sys.argv[1])
#GObject.threads_init()


# Hack to remove the print warning
def enqueue_output(out, tObj,pObj):
    global log_i
    skip_next = False
    for line in iter(out.readline, b''):
        line = line.decode()
        if "Prints, but never reads 'printed" in line:
            skip_next = True
            log_i=0
        elif skip_next:
            skip_next = False
        else:
            GObject.idle_add(tObj.update_log,f"{tObj.log_lines}:"+line)
        log_i=log_i+1
    out.close()
    # in case it dies
    if not os.path.isdir(f"/proc/{pObj.pid}"):
        exit(0)

win.startProcess()
#outp = subprocess.Popen(["python3","-u","G2D/G2D-base.py"],shell=False,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
#t = Thread(target=enqueue_output, args=(outp.stdout,win))
#t.daemon = True
#t.start()

win.show()
Gtk.main()
