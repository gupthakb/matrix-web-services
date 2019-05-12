import sys
from PyQt4 import QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigCan
#from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavTlbar
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib import style
style.use('fivethirtyeight')

class mws_Gui(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self._processes = []
        self.terminal = QWidget(self)
        layout = QVBoxLayout(self)
        self.figure = Figure()
        self.can = FigCan(self.figure)
        #self.tlbar = NavTlbar(self.can, self)
        args = ['-into', str(self.winId()),
        '-geometry',
        '300x15+2+5',
        '+si',
        '-sb',
        '-leftbar',
        '-b', '25',
        '-bc',
        '-e', 'python3 __main__.py'        
        ]
        self._process_start('xterm',args)
        layout.addWidget(self.terminal)
        #layout.addWidget(self.tlbar)
        layout.addWidget(self.can)
        self.ax1 = self.figure.add_subplot(1,1,1)
        self.ani = animation.FuncAnimation(self.figure, self.animate, interval=1000)
        self.showMaximized()

    def animate(self, i):
        graph_data = open('data.txt','r').read()
        lines = graph_data.split('\n')
        xs = []
        ys = []
        for line in lines:
            if len(line) > 1:
                x, y = line.split(',')
                textstr = 'CPU usage = %d\nNum of workers = %d'%(float(x),int(y))
                xs.append(int(x))
                ys.append(int(y))
        self.ax1.clear()
        self.ax1.relim()
        self.ax1.autoscale_view()
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        self.ax1.text(0.05, 0.95, textstr, transform=self.ax1.transAxes, fontsize=14,verticalalignment='top', bbox=props)
        self.ax1.plot(xs, ys)
        self.can.draw()
    def _process_start(self, prog, args):
        self.child = QProcess()
        self._processes.append(self.child)
        self.child.start(prog, args)        
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = mws_Gui()
    main.show()
    sys.exit(app.exec_())