import dro_io
import dro_analysis

@profile
def test_inner():
    dro_loader = dro_io.DroFileIO()
    dro_song = dro_loader.read("pm2_014.dro")
    del dro_loader
    return dro_song
    #ana = dro_analysis.DRODetailedRegisterAnalyzer()
    #result = ana.analyze_dro(dro_song)
    #return result

@profile
def test_tuples():
    data = []
    for i in xrange(400000):
        data.append((i, str(i)))
    return

@profile
def test_slots():
    class Result(object):
        __slots__ = ["intval", "strval"]
        def __init__(self, intval, strval):
            self.intval = intval
            self.strval = strval
    data = []
    for i in xrange(400000):
        data.append(Result(i, str(i)))
    return


@profile
def test_main():
    result = test_inner()
    print result
    del result
    #test_tuples()
    #test_slots()

if __name__ == "__main__": test_main()