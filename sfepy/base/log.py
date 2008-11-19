from base import *
from sfepy.base.tasks import Process, Queue, Empty
from sfepy.base.plotutils import pylab

if pylab:
    import gobject
    from matplotlib.ticker import LogLocator, AutoLocator

class ProcessPlotter( Struct ):
    printer = Output( 'plotter:' )
    output = printer.get_output_function( filename = 'plotter.log' )
    output = staticmethod( output )

    def __init__( self, aggregate = 100 ):
        Struct.__init__( self, aggregate = aggregate )

    def process_command( self, command ):
        self.output( command[0] )

        if command[0] == 'iseq':
            self.iseq = command[1]

        elif command[0] == 'plot':
            ii = self.iseq
            name = self.seq_data_names[ii]
            try:
                ig = self.igs[ii]
                ax = self.ax[ig]
                ax.set_yscale( self.yscales[ig] )
                ax.yaxis.grid( True )
                ax.plot( command[1] )

                if self.yscales[ig] == 'log':
                    ymajor_formatter = ax.yaxis.get_major_formatter()
                    ymajor_formatter.label_minor( True )
                    yminor_locator = LogLocator()
                else:
                    yminor_locator = AutoLocator()
                self.ax[ig].yaxis.set_minor_locator( yminor_locator )
            except:
                print ii, name
                raise

        elif command[0] == 'clear':
            for ig in range( self.n_gr ):
                self.ax[ig].cla()

        elif command[0] == 'legends':
            for ig in range( self.n_gr ):
                self.ax[ig].legend( self.data_names[ig] )

    def terminate( self ):
        if self.ii:
            self.output( 'processed %d commands' % self.ii )
        self.output( 'ended.' )
        pylab.close( 'all' )

    def poll_draw( self ):

        def call_back():
            self.ii = 0
            
            while 1:
                try:
                    command = self.queue.get_nowait()
                except Empty:
                    break

                can_break = False

                if command is None:
                    self.terminate()
                    return False
                elif command[0] == 'continue':
                    can_break = True
                else:
                    self.process_command( command )

                if (self.ii >= self.aggregate) and can_break:
                    break

                self.ii += 1

            self.fig.canvas.draw()
            if self.ii:
                self.output( 'processed %d commands' % self.ii )

            return True

        return call_back
    
    def __call__( self, queue, data_names, igs, seq_data_names, yscales ):
        """Sets-up the plotting window, sets GTK event loop timer callback to
        callback() returned by self.poll_draw(). The callback does the actual
        plotting, taking commands out of `queue`, and is called every second."""
        self.output( 'starting plotter...' )
#        atexit.register( self.terminate )

        self.queue = queue
        self.data_names = data_names
        self.igs = igs
        self.seq_data_names = seq_data_names
        self.yscales = yscales
        self.n_gr = len( data_names )

        self.fig = pylab.figure()

        self.ax = []
        for ig in range( self.n_gr ):
            isub = 100 * self.n_gr + 11 + ig
            self.ax.append( self.fig.add_subplot( isub ) )
        
        self.gid = gobject.timeout_add( 1000, self.poll_draw() )

        self.output( '...done' )


        pylab.show()

class Log( Struct ):
    """Log data and (optionally) plot them in the second process via
    ProcessPlotter."""

    def from_conf( conf, data_names ):
        obj = Log( data_names = data_names, seq_data_names = [], igs = [],
                   data = {}, n_calls = 0 )
        
        for ig, names in enumerate( obj.data_names ):
            for name in names:
                obj.data[name] = []
                obj.igs.append( ig )
                obj.seq_data_names.append( name )
        obj.n_arg = len( obj.igs )
        obj.n_gr = len( obj.data_names )

        if isinstance( conf, dict ):
            get = conf.get
        else:
            get = conf.get_default_attr

        obj.is_plot = get( 'is_plot', True )
        obj.yscales = get( 'yscales', ['linear'] * obj.n_arg )
        obj.aggregate = get( 'aggregate', 100 )

        return obj
    from_conf = staticmethod( from_conf )
    
    def __call__( self, *args, **kwargs ):
        finished = False
        if kwargs:
            if kwargs.has_key( 'finished' ):
                finished = kwargs['finished']

        if finished:
            self.terminate()
            return

        ls = len( args ), self.n_arg
        if ls[0] != ls[1]:
            raise IndexError, '%d == %d' % ls

        for ii, name in enumerate( self.seq_data_names ):
            aux = args[ii]
            if isinstance( aux, nm.ndarray ):
                aux = nm.array( aux, ndmin = 1 )
                if len( aux ) == 1:
                    aux = aux[0]
                else:
                    raise ValueError, 'can log only scalars (%s)' % aux
            self.data[name].append( aux )

        if self.is_plot and (pylab is not None):
            if self.n_calls == 0:
                atexit.register( self.terminate )

                self.plot_queue = Queue()
                self.plotter = ProcessPlotter( self.aggregate )
                self.plot_process = Process( target = self.plotter,
                                             args = (self.plot_queue,
                                                     self.data_names,
                                                     self.igs,
                                                     self.seq_data_names,
                                                     self.yscales) )
                self.plot_process.daemon = True
                self.plot_process.start()

            self.plot_data()
            
        self.n_calls += 1

    def terminate( self ):
        if self.is_plot and (pylab is not None):
            self.plot_queue.put( None )
            self.plot_process.join()
            self.n_calls = 0
            output( 'terminated' )

    def plot_data( self ):
        put =  self.plot_queue.put

        put( ['clear'] )
        for ii, name in enumerate( self.seq_data_names ):
            try:
                put( ['iseq', ii] )
                put( ['plot', nm.array( self.data[name] ) ] )
            except:
                print ii, name, self.data[name]
                raise
        put( ['legends'] )
        put( ['continue'] )
