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


    def __init__(self, powdata, center_freq, span, decimation_factor, state):
        super(SpectrumView, self).__init__()

        self.plot = SpectrumViewPlot(powdata, center_freq, span, decimation_factor, state)
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

    def update_data(self, powdata, center_freq, span, decimation_factor, state):

        if (self.plot.center_freq, self.plot.span, self.plot.decimation_factor) != (
                center_freq, span, decimation_factor):
            self.bottom.update_params(center_freq, span, decimation_factor)
        self.plot.update_data(powdata, center_freq, span, decimation_factor, state)

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

    def __init__(self, powdata, center_freq, span, decimation_factor, state):
        super(SpectrumViewPlot, self).__init__()
        self.powdata = powdata
        self.center_freq = center_freq
        self.span = span
        self.decimation_factor = decimation_factor
        self.peakState = state

    def update_data(self, powdata, center_freq, span, decimation_factor, state):
        self.powdata = powdata
        self.center_freq = center_freq
        self.span = span
        self.decimation_factor = decimation_factor
        self.peakState = state
        self.update()

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawLines(qp)
        qp.end()

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

            if (self.peakState == True):
                # Display Peak Find values
                _max, _min = peakdetect(self.powdata, None, 5, 50)
                xm = [p[0] for p in _max]
                ym = [p[1] for p in _max]                
                qp.setPen(QtCore.Qt.red)
                if (xm != []):
                    maxY = numpy.amax(ym)
                    maxX = numpy.nonzero(self.powdata == maxY)[0][0]
                    pmaxY = height - 1 - (maxY - DBM_BOTTOM) * (
                    float(height - TOP_MARGIN) / (DBM_TOP - DBM_BOTTOM))
                    pmaxX = float(maxX/float(len(x_values))) * (width - 1 - RIGHT_MARGIN)
                    qp.drawRect(pmaxX, pmaxY, 5, 5)
                    # Calculate frequency
                    deltaFrq = float(maxX/float(len(x_values))) * float(self.span)
                    startF = self.center_freq/1e6 - float(self.span/2)
                    peakFrq = (startF + deltaFrq)*1e6
                    peakText = "Peak: %0.6s" % (maxY)
                    frqText = "Freq: %0.7s" % (peakFrq)
                    qp.drawText(200, 18, peakText)
                    qp.drawText(200, 35, frqText)
            qp.setPen(QtCore.Qt.yellow)
            qp.drawText(320, 18, "CF %0.7s" % self.center_freq)
            qp.drawText(320, 35, "Span %0.7s" % self.span)