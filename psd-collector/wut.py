from ingestdaily import PSDExtractor
import logging

log = logging.getLogger("PSD-Collector")
log.setLevel("INFO")
file_handler = logging.FileHandler("rm.temo")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
log.addHandler(file_handler)

filename = "NL.HLB.01.EHZ.D.2021.283"
E = PSDExtractor(log)
E.Process(filename)
