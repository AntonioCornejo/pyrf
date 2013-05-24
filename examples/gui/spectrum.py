import numpy
import itertools
from PySide import QtGui, QtCore
from pyrf.util import peakdetect


TOP_MARGIN = 20
RIGHT_MARGIN = 20
LEFT_AXIS_WIDTH = 70
BOTTOM_AXIS_HEIGHT = 40
AXIS_THICKNESS = 1

DBM_TOP = 20
DBM_BOTTOM = -140
DBM_STEPS = 9

class SpectrumView(QtGui.QWidget):
    """
    A complete spectrum view with left/bottom axis and plot
    """


    def __init__(self, powdata, maxdata, center_freq, span, decimation_factor, enable, find, maxHold, mrk1, mrk2):
        super(SpectrumView, self).__init__()

        self.plot = SpectrumViewPlot(powdata, maxdata,center_freq, span, decimation_factor, enable, find, maxHold, mrk1, mrk2)
        self.left = SpectrumViewLeftAxis()
        self.bottom = SpectrumViewBottomAxis()
        self.bottom.update_params(center_freq, span, decimation_factor)
        self.initUI()

    def initUI(self):
        grid = QtGui.QGridLayout()
        grid.setSpacing(0)
        grid.addWidget(self.left, 0, 0, 2, 1)
        grid.addWidget(self.plot, 0, 1, 1, 1)
        grid.addWidget(self.bottom, 1, 1, 1, 1)
        grid.setRowStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, LEFT_AXIS_WIDTH)
        grid.setRowMinimumHeight(1, BOTTOM_AXIS_HEIGHT)

        grid.setContentsMargins(0, 0, 0, 0)
        self.setLayout(grid)

    def update_data(self, powdata, maxdata, center_freq, span, decimation_factor, enable, find, maxHold, mrk1, mrk2):

        if (self.plot.center_freq, self.plot.span, self.plot.decimation_factor) != (
                center_freq, span, decimation_factor):
            self.bottom.update_params(center_freq, span, decimation_factor)
        self.plot.update_data(powdata, maxdata, center_freq, span, decimation_factor, enable, find, maxHold, mrk1, mrk2)

def dBm_labels(height):
    """
    return a list of (position, label_text) tuples where position
    is a value between 0 (top) and height (bottom).
    """
    # simple, fixed implementation for now
    dBm_labels = [str(d) for d in
        numpy.linspace(DBM_TOP, DBM_BOTTOM, DBM_STEPS)]
    y_values = numpy.linspace(0, height, DBM_STEPS)
    return zip(y_values, dBm_labels)

class SpectrumViewLeftAxis(QtGui.QWidget):
    """
    The left axis of a spectrum view showing dBm range

    This widget includes the space to the left of the bottom axis
    """
    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        size = self.size()
        self.drawAxis(qp, size.width(), size.height())
        qp.end()

    def drawAxis(self, qp, width, height):
        qp.fillRect(0, 0, width, height, QtCore.Qt.black)
        qp.setPen(QtCore.Qt.gray)
        qp.fillRect(
            width - AXIS_THICKNESS,
            TOP_MARGIN,
            AXIS_THICKNESS,
            height - BOTTOM_AXIS_HEIGHT + AXIS_THICKNESS - TOP_MARGIN,
            QtCore.Qt.gray)

        for y, txt in dBm_labels(height - BOTTOM_AXIS_HEIGHT - TOP_MARGIN):
            qp.drawText(
                0,
                y + TOP_MARGIN - 10,
                LEFT_AXIS_WIDTH - 5,
                20,
                QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                txt)
        qp.drawText(10, 170, "dBm")

def MHz_labels(width, center_freq, span, decimation_factor):
    """
    return a list of (position, label_text) tuples where position
    is a value between 0 (left) and width (right).
    """
    df = float(decimation_factor)
    span = float(span)
    offsets = (-2*(span/5), -(span/5), 0, (span/5), 2*(span/5))
    freq_labels = [str(center_freq / 1e6 + d/df) for d in offsets]
    x_values = [(d + span/2) * (width / span) for d in offsets]
    return zip(x_values, freq_labels)

class SpectrumViewBottomAxis(QtGui.QWidget):
    """
    The bottom axis of a spectrum view showing frequencies
    """

    def update_params(self, center_freq, span, decimation_factor):
        self.center_freq = center_freq
        self.span = span
        self.decimation_factor = decimation_factor
        self.update()

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        size = self.size()
        self.drawAxis(qp, size.width(), size.height())
        qp.end()

    def drawAxis(self, qp, width, height):
        qp.fillRect(0, 0, width, height, QtCore.Qt.black)
        qp.setPen(QtCore.Qt.gray)
        qp.fillRect(
            0,
            0,
            width - RIGHT_MARGIN,
            AXIS_THICKNESS,
            QtCore.Qt.gray)

        for x, txt in MHz_labels(
                width - RIGHT_MARGIN,
                self.center_freq,
                self.span,
                self.decimation_factor):
            qp.drawText(
                x - 40,
                5,
                80,
                BOTTOM_AXIS_HEIGHT - 10,
                QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter,
                txt)
        qp.drawText(200, 30, "MHz")
        
class SpectrumViewPlot(QtGui.QWidget):
    """
    The data plot of a spectrum view
    """

    def __init__(self, powdata, maxdata, center_freq, span, decimation_factor, enable, find, maxHold, mrk1, mrk2):
        super(SpectrumViewPlot, self).__init__()
        self.powdata = powdata
        self.maxdata = maxdata
        self.center_freq = center_freq
        self.span = span
        self.decimation_factor = decimation_factor
        self.peakEnable = enable
        self.peakFind = find
        self.peakText = " "
        self.frqText = " "
        self.pmaxX = 0
        self.pmaxY = 0
        self.maxHold = maxHold
        self.currentPos = (0, 0)
        self.x1Click = 0
        self.y1Click = 0
        self.x2Click = 0
        self.y2Click = 0
        self.marker1 = mrk1
        self.marker2 = mrk2

    def update_data(self, powdata, maxdata, center_freq, span, decimation_factor, enable, find, maxHold, mrk1, mrk2):
        self.powdata = powdata
        self.maxdata = maxdata
        self.center_freq = center_freq
        self.span = span
        self.decimation_factor = decimation_factor
        self.peakEnable = enable
        self.peakFind = find
        self.maxHold = maxHold
        self.marker1 = mrk1
        self.marker2 = mrk2
        self.update()

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawLines(qp)
        qp.end()

    def mousePressEvent(self, ev):
        self.currentPos=QtCore.QPoint(ev.pos())
        if (self.marker1 == True and self.marker2 == True):
            # Rotate between the 2 markers
            if (self.lastMarker == 1):
                self.x2Click = self.currentPos.x()
                self.y2Click = self.currentPos.y()
                self.lastMarker = 2
            else:
                self.x1Click = self.currentPos.x()
                self.y1Click = self.currentPos.y()
                self.lastMarker = 1
        elif (self.marker1 == True):
            self.x1Click = self.currentPos.x()
            self.y1Click = self.currentPos.y()
            self.lastMarker = 1
        elif (self.marker2 == True):
            self.x2Click = self.currentPos.x()
            self.y2Click = self.currentPos.y()
            self.lastMarker = 2
        return self.currentPos

    def drawLines(self, qp):
        size = self.size()
        width = size.width()
        height = size.height()
        qp.fillRect(0, 0, width, height, QtCore.Qt.black)

        qp.setPen(QtGui.QPen(QtCore.Qt.gray, 1, QtCore.Qt.DotLine))
        for y, txt in dBm_labels(height - TOP_MARGIN):
            qp.drawLine(
                0,
                y + TOP_MARGIN,
                width - RIGHT_MARGIN - 1,
                y + TOP_MARGIN)
        for x, txt in MHz_labels(
                width - RIGHT_MARGIN,
                self.center_freq,
                self.span,
                self.decimation_factor):
            qp.drawLine(
                x,
                TOP_MARGIN,
                x,
                height - 1)

        qp.setPen(QtCore.Qt.green)

        if (self.powdata != []):
            y_values = height - 1 - (self.powdata - DBM_BOTTOM) * (
                float(height - TOP_MARGIN) / (DBM_TOP - DBM_BOTTOM))
            x_values = numpy.linspace(0, width - 1 - RIGHT_MARGIN,
                len(self.powdata))

            path = QtGui.QPainterPath()
            points = itertools.izip(x_values, y_values)
            path.moveTo(*next(points))
            for x,y in points:
                path.lineTo(x, y)
            qp.drawPath(path)

            if (self.peakEnable == True):
                # Display Peak Find value
                qp.setPen(QtCore.Qt.red)
                if (self.peakFind == True):
                    _max, _min = peakdetect(self.powdata, None, 5, 10)
                    xm = [p[0] for p in _max]
                    ym = [p[1] for p in _max]                
                    if (xm != []):
                        maxY = numpy.amax(ym)
                        maxX = numpy.nonzero(self.powdata == maxY)[0][0]
                        self.pmaxY = height - 1 - (maxY - DBM_BOTTOM) * (
                            float(height - TOP_MARGIN) / (DBM_TOP - DBM_BOTTOM))
                        self.pmaxX = float(maxX/float(len(x_values))) * (width - 1 - RIGHT_MARGIN)
                        # Calculate frequency
                        deltaFrq = float(maxX/float(len(x_values))) * float(self.span)
                        startF = self.center_freq/1e6 - float(self.span/2)
                        peakFrq = (startF + deltaFrq)*1e6
                        self.peakText = "Peak: %0.6s" % (maxY)
                        self.frqText = "Freq: %0.7s" % (peakFrq)
                # Display last peak value found
                qp.drawRect(self.pmaxX, self.pmaxY, 5, 5)
                qp.drawText(220, 18, self.peakText)
                qp.drawText(220, 35, self.frqText)
            else:
                self.pmaxX = 0
                self.pmaxY = 0
                self.peakText = " "
                self.frqText = " "

            if (self.maxHold == True):
                # Display Max Hold plot
                qp.setPen(QtCore.Qt.blue)
                hold_y_values = height - 1 - (self.maxdata - DBM_BOTTOM) * (
                    float(height - TOP_MARGIN) / (DBM_TOP - DBM_BOTTOM))
                hold_x_values = numpy.linspace(0, width - 1 - RIGHT_MARGIN,
                    len(self.maxdata))
                path = QtGui.QPainterPath()
                points = itertools.izip(hold_x_values, hold_y_values)
                path.moveTo(*next(points))
                for x,y in points:
                    path.lineTo(x, y)
                qp.drawPath(path)
                    
            qp.setPen(QtCore.Qt.yellow)
            qp.drawText(320, 18, "CF: %0.7s" % self.center_freq)
            qp.drawText(320, 35, "Span: %0.7s" % self.span)

            if (self.marker1 == True):
                qp.setPen(QtGui.QColor('#FF9900'))
                qp.drawRect(self.x1Click, self.y1Click, 3, 3)
                y1 = -(((self.y1Click - height + 1) / 
                    (float(height - TOP_MARGIN) / (DBM_TOP - DBM_BOTTOM))) - DBM_BOTTOM)
                x1 = float(self.x1Click /float(width - 1 - RIGHT_MARGIN))
                # Calculate frequency
                delta = float(x1 * float(self.span))
                start = self.center_freq/1e6 - float(self.span/2)
                marker1Frq = (start + delta)*1e6
                marker1Text = "Mrk 1: %0.6s" % (y1)
                frq1Text = "Freq: %0.7s" % (marker1Frq)
                qp.drawText(25, 18, marker1Text)
                qp.drawText(25, 35, frq1Text)
            else:
                self.x1Click = 0
                self.y1Click = 0

            if (self.marker2 == True):
                qp.setPen(QtGui.QColor('#CC0099'))
                qp.drawRect(self.x2Click, self.y2Click, 3, 3)
                y2 = -(((self.y2Click - height + 1) / 
                    (float(height - TOP_MARGIN) / (DBM_TOP - DBM_BOTTOM))) - DBM_BOTTOM)
                x2 = float(self.x2Click /float(width - 1 - RIGHT_MARGIN))
                # Calculate frequency
                delta = float(x2 * float(self.span))
                start = self.center_freq/1e6 - float(self.span/2)
                marker2Frq = (start + delta)*1e6
                marker2Text = "Mrk 2: %0.6s" % (y2)
                frq2Text = "Freq: %0.7s" % (marker2Frq)
                qp.drawText(120, 18, marker2Text)
                qp.drawText(120, 35, frq2Text)
            else:
                self.x2Click = 0
                self.y2Click = 0
