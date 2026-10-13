"""Step 1 of the round trip (runs in jupyter:smartbuilding-surrogate, python 3.11, bdopt 0.2.0).

usage: python roundtrip_save.py MODELS_DIR SAVED_DIR
Loads every *.idf in MODELS_DIR with bdopt, saves it with bdopt into SAVED_DIR under the same name,
prints one line per model with the object count seen by bdopt and the time taken.
"""
import sys, time, glob, os
import bdopt

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for path in sorted(glob.glob(os.path.join(src, '*.idf'))):
    t = time.time()
    try:
        idf = bdopt.load_idf(path)
        out = idf.save(os.path.join(dst, os.path.basename(path)))
        n = len(idf.objects)
        print('OK  %-40s bdopt objects=%s version=%s %.1fs' % (os.path.basename(path), n, idf.version, time.time() - t))
    except Exception as e:  # report, keep going
        print('ERR %-40s %s: %s' % (os.path.basename(path), type(e).__name__, e))
