# -*- coding: utf-8 -*- 
# -----------------------------------------------------------------------------
#    Name: ThinkRF Sweep Demo GUI
#    Functionality:  This script extends the functionality of existing GUI
#                    demo, to add the sweep functionality.
#    Author:   Antonio Martinez
#    Date:     11/02/2013
#    Version:  0.0
#    Modified: 12/02/2013 - Added tab widgets.
#    Comments:
# -----------------------------------------------------------------------------
from __future__ import unicode_literals
import sys
import socket

from PySide import QtGui, QtCore
from spectrum import SpectrumView
from util import frequency_text

from pyrf.devices.thinkrf import WSA4000
from pyrf.util import read_data_and_reflevel, read_data_and_reflevel_sweep 
from pyrf.numpy_util import compute_fft, compute_avg_fft, get_iq_data, compute_fft_noLog, compute_dBm
from numpy import concatenate, amax, mean
import numpy
import time
import math

DEVICE_FULL_SPAN = 125e6
REFRESH_CHARTS = 0.05
FULLBAND = 100
HALFBAND = 45
MIN_START_FREQ = 40
MIN_SPAN = 10
MAX_SPAN = 9900
START_SWEEP = 2000
		
# -----------------------------------------------------------------------------
#    Class: MainWindow
# -----------------------------------------------------------------------------
class MainWindow(QtGui.QMainWindow):

    def __init__(self, name=None, parent=None):
        super(MainWindow, self).__init__()
        self.initUI()
        self.dut = None
		# Connect to box
        if len(sys.argv) > 1:
            dut = self.open_device(sys.argv[1])
        else:
            dut = self.open_device_dialog()
        self.create_main_frame(dut)
        self.show()
		
    def create_main_frame(self, mfdut):        
        tabs = QtGui.QTabWidget()
        tabs.addTab(MainPanel(mfdut), 'MainPanel')
        self.setCentralWidget(tabs)
		
    def initUI(self):
        openAction = QtGui.QAction('&Open Device', self)
        openAction.triggered.connect(self.open_device_dialog)
        exitAction = QtGui.QAction('&Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.close)
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addAction(exitAction)
        self.setWindowTitle('ThinkRF WSA4000')

    def open_device_dialog(self):
        name, ok = QtGui.QInputDialog.getText(self, 'Open Device',
            'Enter a hostname or IP address:')
        while True:
            if not ok:
                return
            try:
                dut = self.open_device(name)
                break
            except socket.error:
                name, ok = QtGui.QInputDialog.getText(self, 'Open Device',
                    'Connection Failed, please try again\n\n'
                    'Enter a hostname or IP address:')
        return dut

    def open_device(self, name):
        dut = WSA4000()
        dut.connect(name)
        dut.request_read_perm()
        if '--reset' in sys.argv:
            dut.reset()
        self.dut = dut
        self.setCentralWidget(MainPanel(dut))
        self.setWindowTitle('ThinkRF WSA4000: %s' % name)
        return dut

class MainPanel(QtGui.QWidget):

    def __init__(self, dut):
        super(MainPanel, self).__init__()
        self.dut = dut
        self.get_freq_mhz()
        self.get_decimation()
        self.decimation_points = None
        if self.dut.sweep_status() == 'RUNNING':
            self.dut.sweep_stop()
            self.dut.flush_captures()    # Flush old data
        self.sweepMode = False
        self.spanBuf = []
        self.packets = 1
        self.pkts = 1
        self.count = 0
        self.vbw_changed = True
        self.ifgain = 0
        self.i_aggr_data = []
        self.q_aggr_data = []
        self.startFrqSweep = START_SWEEP
        self.stopFrqSweep = START_SWEEP + FULLBAND
        self.avgType = "Pwr Avg"
        self.suspendView = False
        data, reflevel = read_data_and_reflevel(dut)
        self.screen = SpectrumView(
            compute_fft(dut, data, reflevel),
            self.center_freq,
            DEVICE_FULL_SPAN/1e6,
            self.decimation_factor)
        self.initUI()

    def initUI(self):
        grid = QtGui.QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(self.screen, 0, 0, 14, 1)
        grid.setColumnMinimumWidth(0, 500)

        y = 0
        grid.addWidget(self._radio_title(), y, 1, 1, 4)
        y += 1
        grid.addWidget(self._antenna_control(), y, 1, 1, 1)
        grid.addWidget(self._bpf_control(), y, 3, 1, 2)
        y += 1
        grid.addWidget(self._gain_control(), y, 1, 1, 1)
        grid.addWidget(QtGui.QLabel('IF Gain:'), y, 3, 1, 1)
        grid.addWidget(self._ifgain_control(), y, 4, 1, 1)
        y += 1
        grid.addWidget(self._frequency_title(), y, 1, 1, 4)
        y += 1
        # Span control
        grid.addWidget(self._span_control(), y, 1, 1, 1)
        self.spanLine = QtGui.QLineEdit("100.0")
        self.span = float(self.spanLine.text())
        spanLine, steps, freq_plus, freq_minus = self._freq_controls(self.spanLine)
        grid.addWidget(self.spanLine, y, 2, 1, 2)
        grid.addWidget(QtGui.QLabel('MHz'), y, 4, 1, 1)
        self.span_y = y
        y += 1
        # Center frequency control
        grid.addWidget(self._centerFreq_control(), y, 1, 1, 1)
        self.cfLine = QtGui.QLineEdit("2400.0")
        self.centerFrq = float(self.cfLine.text())
        grid.addWidget(self.cfLine, y, 2, 1, 2)
        grid.addWidget(QtGui.QLabel('MHz'), y, 4, 1, 1)
        self.cf_y = y		
        y += 1
        # Start frequency control
        grid.addWidget(self._startFreq_control(), y, 1, 1, 1)
        self.startFrqLine = QtGui.QLineEdit("2350.0")
        self.startFrq = float(self.startFrqLine.text())
        grid.addWidget(self.startFrqLine, y, 2, 1, 2)
        grid.addWidget(QtGui.QLabel('MHz'), y, 4, 1, 1)
        self.start_y = y
        y += 1
        # Stop frequency control
        grid.addWidget(self._stopFreq_control(), y, 1, 1, 1)
        self.stopFrqLine = QtGui.QLineEdit("2450.0")
        self.stopFrq = float(self.stopFrqLine.text())
        grid.addWidget(self.stopFrqLine, y, 2, 1, 2)
        grid.addWidget(QtGui.QLabel('MHz'), y, 4, 1, 1)
        self.stop_y = y		
        y += 1
        # Band selection control
        band = self._band_control()
        grid.addWidget(band, y, 2, 1, 1)
        self.set_freq_mhz(self.centerFrq)
        # Resolution Bandwidth control
        self.rbw = self._rbw_control()
        grid.addWidget(self.rbw, y, 1, 1, 1)
        y += 1		
        # Video Bandwidth control
        grid.addWidget(self._vbw_control(), y, 1, 1, 1)
        grid.addWidget(self._avg_control(), y, 2, 1, 1)
        self.vbw_y = y
        y += 1
        grid.addWidget(self._frequency_adjust_title(), y, 1, 1, 4)
        y += 1
        self.adj_y = y
        grid.addWidget(steps, y, 2, 1, 2)
        grid.addWidget(freq_minus, y, 1, 1, 1)
        grid.addWidget(freq_plus, y, 4, 1, 1)

        self.setLayout(grid)
        self.grid = grid
        self.show()
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.update_charts)
        timer.start(REFRESH_CHARTS)

    def update_charts(self):
        if self.dut is None:
            return
        self.update_screen()

    def _radio_title(self):
        s = "───────────── RADIO SETTINGS ─────────────"
        s_html = "<font color=black size=3> {} </font>".format(s)
        label = QtGui.QLabel(s_html)
        return label

    def _antenna_control(self):
        antenna = QtGui.QComboBox(self)
        antenna.addItem("Antenna 1")
        antenna.addItem("Antenna 2")
        antenna.setCurrentIndex(self.dut.antenna() - 1)
        def new_antenna():
            if (self.sweepMode == True):
                self.stopSweep()
                self.dut.antenna(int(antenna.currentText().split()[-1]))
                self.define_sweep_entry()
                self.startSweep()
            else:
                self.dut.antenna(int(antenna.currentText().split()[-1]))
        antenna.currentIndexChanged.connect(new_antenna)
        return antenna

    def _bpf_control(self):
        bpf = QtGui.QComboBox(self)
        bpf.addItem("BPF On")
        bpf.addItem("BPF Off")
        bpf.setCurrentIndex(0 if self.dut.preselect_filter() else 1)
        def new_bpf():
            if (self.sweepMode == True):
                self.stopSweep()
                self.dut.preselect_filter("On" in bpf.currentText())
                self.define_sweep_entry()
                self.startSweep()
            else:
                self.dut.preselect_filter("On" in bpf.currentText())
        bpf.currentIndexChanged.connect(new_bpf)
        return bpf

    def _gain_control(self):
        gain = QtGui.QComboBox(self)
        gain_values = ['High', 'Med', 'Low', 'VLow']
        for g in gain_values:
            gain.addItem("RF Gain: %s" % g)
        gain_index = [g.lower() for g in gain_values].index(self.dut.gain())
        gain.setCurrentIndex(gain_index)
        def new_gain():
            if (self.sweepMode == True):
                self.stopSweep()
                self.gain = self.dut.gain(gain.currentText().split()[-1].lower())
                self.define_sweep_entry()
                self.startSweep()
            else:
                self.gain = self.dut.gain(gain.currentText().split()[-1].lower())
        gain.currentIndexChanged.connect(new_gain)
        self.gain = gain_values[gain_index]		
        return gain

    def _ifgain_control(self):
        ifgain = QtGui.QSpinBox(self)
        ifgain.setRange(-10, 34)
        ifgain.setSuffix(" dB")
        ifgain.setValue(int(self.dut.ifgain()))
        def new_ifgain():
            if (self.sweepMode == True):
                self.stopSweep()
                self.ifgain = self.dut.ifgain(ifgain.value())
                self.define_sweep_entry()
                self.startSweep()
            else:
                self.ifgain = self.dut.ifgain(ifgain.value())
        ifgain.valueChanged.connect(new_ifgain)
        return ifgain

    def _frequency_title(self):
        s = "─────────── FREQUENCY SETTINGS ───────────"
        s_html = "<font color=black size=3> {} </font>".format(s)
        label = QtGui.QLabel(s_html)
        return label

    def _span_control(self):
        spanButton = QtGui.QPushButton('Span')
        spanButton.clicked.connect(self.spanButtonClicked)
        self.spanButton = spanButton
        return spanButton
   
    def spanButtonClicked(self):
        self.spanLine, steps, freq_plus, freq_minus = self._freq_controls(self.spanLine)
        self.grid.addWidget(self.spanLine, self.span_y, 2, 1, 2)
        self.grid.addWidget(steps, self.adj_y, 2, 1, 2)
        self.grid.addWidget(freq_minus, self.adj_y, 1, 1, 1)
        self.grid.addWidget(freq_plus, self.adj_y, 4, 1, 1)
		
    def _centerFreq_control(self):
        cFreqButton = QtGui.QPushButton('Center Freq')
        self.cFreqButton = cFreqButton
        cFreqButton.clicked.connect(self.cfButtonClicked)
        return cFreqButton	

    def cfButtonClicked(self):
        self.cfLine, steps, freq_plus, freq_minus = self._freq_controls(self.cfLine)
        self.grid.addWidget(self.cfLine, self.cf_y, 2, 1, 2)		
        self.grid.addWidget(steps, self.adj_y, 2, 1, 2)
        self.grid.addWidget(freq_minus, self.adj_y, 1, 1, 1)
        self.grid.addWidget(freq_plus, self.adj_y, 4, 1, 1)
		
    def _startFreq_control(self):
        startFreqButton = QtGui.QPushButton('Start Freq')
        startFreqButton.clicked.connect(self.startFreqButtonClicked)
        return startFreqButton

    def startFreqButtonClicked(self):
        self.startFrqLine, steps, freq_plus, freq_minus = self._freq_controls(self.startFrqLine)
        self.grid.addWidget(self.startFrqLine, self.start_y, 2, 1, 2)		
        self.grid.addWidget(steps, self.adj_y, 2, 1, 2)
        self.grid.addWidget(freq_minus, self.adj_y, 1, 1, 1)
        self.grid.addWidget(freq_plus, self.adj_y, 4, 1, 1)

    def _stopFreq_control(self):
        stopFreqButton = QtGui.QPushButton('Stop Freq')
        stopFreqButton.clicked.connect(self.stopFreqButtonClicked)		
        return stopFreqButton

    def stopFreqButtonClicked(self):
        self.stopFrqLine, steps, freq_plus, freq_minus = self._freq_controls(self.stopFrqLine)
        self.grid.addWidget(self.stopFrqLine, self.stop_y, 2, 1, 2)		
        self.grid.addWidget(steps, self.adj_y, 2, 1, 2)
        self.grid.addWidget(freq_minus, self.adj_y, 1, 1, 1)
        self.grid.addWidget(freq_plus, self.adj_y, 4, 1, 1)

    def _rbw_control(self):
#        decimation_values = [1] + [2 ** x for x in range(2, 10)]
#        for d in decimation_values:
#            span.addItem("Span: %s" % frequency_text(DEVICE_FULL_SPAN / d))
#        span.setCurrentIndex(decimation_values.index(self.dut.decimation()))
        rbw = QtGui.QComboBox(self)
        points_values = [2 ** x for x in range(8, 16)]
        rbw.addItems([str(p) for p in points_values])
        def build_rbw():
            d = self.decimation_factor
            for i, p in enumerate(points_values):
                r = DEVICE_FULL_SPAN / d / p
                rbw.setItemText(i, "RBW: %s" % frequency_text(r))
                if self.decimation_points and self.decimation_points == d * p:
                    rbw.setCurrentIndex(i)
            self.points = points_values[rbw.currentIndex()]
        build_rbw()
        def select_rbw_vs_span(self):
            if (self.span*1e6 < 1e9):
                return True    # Below 1 Ghz any RBW value is allowed
            if (self.span*1e6 >= 1e9):    # Above 1 GHz, maximum RBW is 1024
                if (self.points > 1024):
                    return False
                else:
                    return True
        def new_rbw():
            if (self.sweepMode == True):
                self.points = points_values[rbw.currentIndex()]
                if (select_rbw_vs_span(self)):
                    self.stopSweep()
                    self.decimation_points = self.decimation_factor * self.points
                    self.define_sweep_entry()
                    self.startSweep()
                else:
                    rbw.setCurrentIndex(points_values.index(1024))
                    self.popup_window = PopupWindow("RBW selected is too high for current span.")
            else:
                self.points = points_values[rbw.currentIndex()]
                self.decimation_points = self.decimation_factor * self.points
        rbw.setCurrentIndex(points_values.index(1024))
        new_rbw()
        rbw.currentIndexChanged.connect(new_rbw)
        return rbw

    def _band_control(self):
        band = QtGui.QComboBox(self)
        band_values = [45, 100]
        band.addItems(["Band: %s MHz" % str(p) for p in band_values])
        band.setCurrentIndex(band_values.index(100))
        def new_band():
            self.band = band_values[band.currentIndex()]
            self.recalculate_span()
            self.set_freq_mhz(self.centerFrq)
        new_band()
        band.currentIndexChanged.connect(new_band)
        return band

    def _vbw_control(self):
        vbw = QtGui.QComboBox(self)
        avg_packets = [2 ** x for x in range(0, 7)]
        vbw.addItems([str(p) for p in avg_packets])
        def build_vbw():
            d = self.decimation_factor
            for i, p in enumerate(avg_packets):
                v = DEVICE_FULL_SPAN / d / self.points / p
                vbw.setItemText(i, "VBW: %s" % frequency_text(v))
#                if self.decimation_points and self.decimation_points == d * p:
                vbw.setCurrentIndex(i)
            self.packets = avg_packets[vbw.currentIndex()]
        build_vbw()
        def new_vbw():
            self.packets = avg_packets[vbw.currentIndex()]
            self.vbw_changed = True
#            self.decimation_points = self.decimation_factor * self.points
        vbw.setCurrentIndex(avg_packets.index(2**0))
        new_vbw()
        self.vbw = vbw
        vbw.currentIndexChanged.connect(new_vbw)
        return vbw

    def _avg_control(self):
        avg = QtGui.QComboBox(self)
        avg_values = ["Pwr Avg", "Log Avg"]
        avg.addItems(["%s" % str(p) for p in avg_values])
        avg.setCurrentIndex(avg_values.index("Pwr Avg"))
        def new_avg():
            self.avgType = avg_values[avg.currentIndex()]
        new_avg()
        self.avg = avg
        avg.currentIndexChanged.connect(new_avg)
        return avg

    def _frequency_adjust_title(self):
        s = "──────────── FREQUENCY ADJUST ────────────"
        s_html = "<font color=black size=3> {} </font>".format(s)
        label = QtGui.QLabel(s_html)
        return label
        steps = QtGui.QComboBox(self)
        steps.addItem("Adjust: 1 MHz")
        steps.addItem("Adjust: 2.5 MHz")
        steps.addItem("Adjust: 10 MHz")
        steps.addItem("Adjust: 25 MHz")
        steps.addItem("Adjust: 100 MHz")
        steps.setCurrentIndex(2)

    def _freq_controls(self, freq):
        def read_freq():
            if freq == self.spanLine:
                freq.setText("%0.1f" % self.span)
            elif freq == self.cfLine:
                freq.setText("%0.1f" % self.centerFrq)
            elif freq == self.startFrqLine:
                freq.setText("%0.1f" % self.startFrq)
            elif freq == self.stopFrqLine:
                freq.setText("%0.1f" % self.stopFrq)
        read_freq()
        def recalculate_freq():
            if (freq == self.spanLine or freq == self.cfLine):
                self.startFrq = self.centerFrq - self.span/2
                self.startFrqLine.setText("%0.1f" % self.startFrq)
                self.stopFrq = self.centerFrq + self.span/2
                self.stopFrqLine.setText("%0.1f" % self.stopFrq)
            elif (freq == self.startFrqLine or freq == self.stopFrqLine):
                self.span = self.stopFrq - self.startFrq
                self.spanLine.setText("%0.1f" % self.span)
                self.centerFrq = self.startFrq + self.span/2
                self.cfLine.setText("%0.1f" % self.centerFrq)
        def display_freq():
                self.startFrqLine.setText("%0.1f" % self.startFrq)
                self.stopFrqLine.setText("%0.1f" % self.stopFrq)
                self.spanLine.setText("%0.1f" % self.span)
                self.cfLine.setText("%0.1f" % self.centerFrq)
        def correct_freq():
            if (self.startFrq < MIN_START_FREQ):
                self.startFrq = MIN_START_FREQ
                freq.setText("%0.1f" % self.startFrq)
                self.popup_window = PopupWindow("Start frequency cannot be less than 45 MHz.")
                self.stopFrq = self.startFrq + MIN_SPAN
                self.span = MIN_SPAN
                self.centerFrq = self.startFrq + self.span/2
                display_freq()
            if (self.stopFrq <= self.startFrq):
                self.stopFrq = self.startFrq + MIN_SPAN
                freq.setText("%0.1f" % self.stopFrq)
                self.span = MIN_SPAN
                self.centerFrq = self.startFrq + self.span/2                
                display_freq()                
                self.popup_window = PopupWindow("Stop frequency cannot be lower than start frequency.")
            if (self.span > MAX_SPAN):
                self.span = MIN_START_FREQ
                freq.setText("%0.1f" % self.span)
                self.popup_window = PopupWindow("Span cannot exceed 9.9 GHz.")	
            if (self.centerFrq < MIN_START_FREQ + MIN_SPAN/2):
                self.centerFrq = MIN_START_FREQ + MIN_SPAN/2
                freq.setText("%0.1f" % self.centerFrq)		
                self.popup_window = PopupWindow("Center frequency cannot be less than 110 MHz.")
        def correct_rbw():
            if (self.span*1e6 >= 1e9):
                if (self.points > 1024):
                    self.rbw.setCurrentIndex(2)
                    self.popup_window = PopupWindow("RBW modified for current span.")
        def write_freq():
            try:
                f = float(freq.text())
            except ValueError:
                return
            if freq == self.spanLine:
                self.span = f    # save modified value
            elif freq == self.cfLine:
                self.centerFrq = f
            elif freq == self.startFrqLine:
                self.startFrq = f
            elif freq == self.stopFrqLine:
                self.stopFrq = f
            recalculate_freq()
            correct_freq()
            self.set_freq_mhz(self.centerFrq)
            self.recalculate_span()
            correct_rbw()
        freq.editingFinished.connect(write_freq)

        steps = QtGui.QComboBox(self)
        steps.addItem("Adjust: 1 MHz")
        steps.addItem("Adjust: 2.5 MHz")
        steps.addItem("Adjust: 10 MHz")
        steps.addItem("Adjust: 25 MHz")
        steps.addItem("Adjust: 100 MHz")
        steps.setCurrentIndex(2)
        def freq_step(factor):
            try:
                f = float(freq.text())
            except ValueError:
                return read_freq()
            delta = float(steps.currentText().split()[1]) * factor
            freq.setText("%0.1f" % (f + delta))
            write_freq()
        freq_minus = QtGui.QPushButton('-')
        freq_minus.clicked.connect(lambda: freq_step(-1))
        freq_plus = QtGui.QPushButton('+')
        freq_plus.clicked.connect(lambda: freq_step(1))

        return freq, steps, freq_plus, freq_minus

    def recalculate_span(self):
        if (self.span > self.band):
            if (self.band == HALFBAND):
                self.startFrqSweep = self.startFrq + HALFBAND
                self.stopFrqSweep = self.stopFrq + HALFBAND
            else:
                self.startFrqSweep = self.startFrq + FULLBAND/2
                self.stopFrqSweep = self.stopFrq + FULLBAND/2
            self.stopSweep()
            self.define_sweep_entry()
            self.startSweep()
        else:
            self.stopSweep()

    def define_sweep_entry(self):
        count = self.dut.sweep_count()
        if (count > 0):
            self.dut.sweep_clear()    # Delete existing entries
        self.entry = self.dut.sweep_default_entry()
        self.entry.fstart = float(self.startFrqSweep * 1e6)
        self.entry.fstop = float(self.stopFrqSweep * 1e6)
        self.entry.fstep = self.band * 1e6
        self.step = self.band
        self.entry.antenna = self.dut.antenna()
        self.entry.spp = self.points
        self.entry.ppb = 1
        self.entry.gain = self.gain
        self.entry.ifgain = self.ifgain
#        print (self.entry)
        # Add entry in device
        self.dut.sweep_add(self.entry)

    def startSweep(self):
        # Check if entries were created for list
        count = self.dut.sweep_count()
        if (count > 0):
            self.sweepMode = True   # Set sweep as active mode
            self.suspendView = True
            self.dut.flush_captures()
            self.dut.system_flush()
            self.dut.sweep_start()
            self.spanBuf = []
            # Hide VBW/AVG combo boxes
            self.vbw.hide()
            self.avg.hide()

    def stopSweep(self):
        # Check if device is in sweep mode
        if (self.sweepMode == True):
            self.sweepMode = False   # Set sweep as inactive mode
            self.suspendView = True
            self.dut.sweep_stop()
            self.count = 0
            self.spanBuf = []
            self.dut.flush_captures()    # Flush old data
            self.dut.system_flush()
            self.set_freq_mhz(self.centerFrq)
            self.vbw.show()
            self.avg.show()

    def update_screen(self):
        reflevel = None
        if (self.sweepMode == False):
            while (reflevel == None):
                data, reflevel = read_data_and_reflevel(
                    self.dut,
                    self.points
                    )
            # Average data from N packets:
            if ((self.vbw_changed == True) and (self.count == 0)):
                self.vbw_changed = False
                self.pkts = self.packets
            arrayData = self.average_fft(data, reflevel)
            if (arrayData != []):
                spanData = self.select_samples_trace(arrayData, self.band)
                self.screen.update_data(
                    spanData,
                    self.centerFrq*1e6,
                    self.span,
                    self.decimation_factor)
        else:
            while (reflevel == None):
                data, reflevel, start, stop, rem, stid = read_data_and_reflevel_sweep(
                    self.dut,
                    self.entry.fstart,
                    self.entry.fstop,
                    self.step
                )
             # Compute data from packets
            arrayData = compute_fft(self.dut, data, reflevel)
            if (self.span*1e6 <= 1e9):
                sliceSize = 1
            elif (self.span*1e6 > 1e9):
                sliceSize = 8
            elif (self.span*1e6 > 2*1e9):
                sliceSize = 16
            elif (self.span*1e6 > 4*1e9):
                sliceSize = 32
            if (sliceSize > 1):
                arrayData = self.get_max(arrayData, sliceSize)
            # Select samples from array and aggregate FFT data
            stepData = self.select_samples_sweep(arrayData, start, stop, self.step, rem)
            if start == True:
                self.spanBuf = []
                start = False
                if stid == True:
                    self.suspendView = False
            self.spanBuf = concatenate([self.spanBuf, stepData])
            if  stop == True:
                stop = False
                if self.suspendView == False:                        
                    self.screen.update_data(
                        self.spanBuf,
                        self.centerFrq*1e6,
                        self.span,
                        self.decimation_factor)
        
    def average_fft(self, data, ref):
        arrayData = []
        if self.avgType == "Pwr Avg":
            aData = compute_fft_noLog(data)
        elif self.avgType == "Log Avg":
            aData = compute_fft(self.dut, data, ref)
        self.spanBuf = concatenate([self.spanBuf, aData])
        self.count = self.count + 1
        if (self.count == self.pkts):
            if self.avgType == "Pwr Avg":
                fftAvg = self.get_avg(self.spanBuf, self.pkts)
                arrayData = compute_dBm(fftAvg, ref, self.dut.ADC_DYNAMIC_RANGE)
            elif self.avgType == "Log Avg":
                arrayData = self.get_avg(self.spanBuf, self.pkts)
            self.spanBuf = []
            self.count = 0
        return arrayData

    def select_samples_trace(self, data, band):
        N = len(data)     # Get array length (number of samples in data array)
        halfIndex = int(N/2)   # Get half array index
        # Calculate ratio of span against maximum bandwidth
        ratio = self.span*1e6/DEVICE_FULL_SPAN
        if (band == FULLBAND):
            # Calculate indexes of passband frequencies
            firstIndex = int(N * ((1 - ratio)/2))
            lastIndex = int(N * (1 - (1 - ratio)/2))		
            # Remove stopband frequencies
            data = data[firstIndex:lastIndex]
        elif (band == HALFBAND):
            firstIndex = halfIndex - int(N * ratio)
            # Remove second half of data set plus stopband frequencies
            data = data[firstIndex-1:halfIndex-1]
        return data
					
    def select_samples_sweep(self, data, start, stop, step, rem):
        """
        
        Select samples from data array, that correspond to passband
		frequencies of step bandwidth. Handles special cases for start
		and stop group of frequenceis.

        :param data: numpy array of dBm values from 'compute_fft'
        :param start: boolean that indicates that data belongs to
		first group of frequencies
        :param stop: boolean that indicates that data belongs to
        last group of frequencies
        :param step: size of step frequency bandwidth (45 or 100 MHz)
		:param rem:  remaining bandwidth in last group of frequencies.  
        :returns: data (selected passband frequency samples)
        """
        N = len(data)     # Get array length (number of samples in data array)
        halfIndex = int(N/2)   # Get half array index
        # Calculate ratio of step against maximum bandwidth
        ratio = step*1e6/DEVICE_FULL_SPAN    # 0.8 (100 MHz) or 0.36 (45 Mhz)
        # Calculate indexes of passband frequencies
        firstIndex = int(N * ((1 - ratio)/2))
        lastIndex = int(N * (1 - (1 - ratio)/2))
        # Handling for 100 MHz step
        if (step == FULLBAND):
            if stop == False:        
                # Select passband frequencies
                data = data[firstIndex:lastIndex]
            else:
                # Last index depends on stop frequency
                remIndex = int(N * rem/DEVICE_FULL_SPAN)
                data = data[firstIndex:remIndex]
        elif (step == HALFBAND):
            firstIndex = halfIndex - int(N * ratio)
            # Use only upper half of bandwidth
            if start == True:
                # Remove second half of data set plus stopband frequencies
                data = data[firstIndex-1:halfIndex-1]
            elif stop == True:
                # Last index depends on stop frequency
                remIndex = int(N * rem/DEVICE_FULL_SPAN)
                # Remove second half of data set plus stopband frequencies
                data = data[firstIndex-1:firstIndex+remIndex-1]
            else:
                # For other groups, select lower half of step bandwidth
                data = data[firstIndex-1:halfIndex-1]
        return data

    def get_max(self, data, slice):
        # Slice data array and find max value on each slice
        N = len(data)     # Get number of samples in data array
        part = data.reshape((N/slice, slice))
        a = amax(part, axis=1)
        a.flatten()
        return a

    def get_avg(self, data, pkts):
        # Slice data array and find average value across N packets
        N = len(data)     # Get number of samples in data array
        if (pkts == 1):
            return data
        if (pkts > 1):
            part = data.reshape((pkts, N/pkts))
            a = mean(part, axis=0)
            return a

    def get_freq_mhz(self):
        self.center_freq = self.dut.freq()
        return self.center_freq / 1e6

    def set_freq_mhz(self, f):
	    # Center frequency depends on band used
        if (self.band == FULLBAND):
            self.center_freq = f * 1e6
        else:
            self.center_freq = (f + self.span/2) * 1e6
        self.dut.freq(self.center_freq)

    def get_decimation(self):
        d = self.dut.decimation()
        self.decimation_factor = 1 if d == 0 else d

    def set_decimation(self, d):
        self.decimation_factor = 1 if d == 0 else d
        self.dut.decimation(d)

class PopupWindow(QtGui.QWidget):

    def __init__(self, message, parent=None):
        super(PopupWindow, self).__init__(parent)

        self.setWindowTitle('Popup Window')
        layout = QtGui.QGridLayout()
        line = QtGui.QLabel(message)
        layout.addWidget(line, 0, 0)
        self.setLayout(layout)
        self.show()
