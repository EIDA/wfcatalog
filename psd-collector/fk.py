import os

aroot = "/home/orfeus/lol"

filez = []

for root, dirs, files in os.walk(aroot):
  print root, files
  for name in files:
    filez.append(os.path.join(root, name))

print filez
