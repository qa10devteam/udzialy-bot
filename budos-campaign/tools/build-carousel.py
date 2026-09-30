# Builds carousel.html from carousel.src.html: inlines the logo paths, the original cover (reference only) and the QA10 mark.
import base64, io, pathlib
from PIL import Image
root = pathlib.Path(__file__).resolve().parent.parent
paths = dict(l.split('=', 1) for l in (root / 'brand' / 'budos-logo-paths.txt').read_text().strip().split('\n') if '=' in l and not l.startswith('W='))
buf = io.BytesIO(); Image.open(root / 'brand' / 'premiera-okladka-oryginal.png').convert('RGB').save(buf, 'JPEG', quality=86)
cover = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
qa10 = 'data:image/png;base64,' + base64.b64encode((root / 'brand' / 'qa10-by.png').read_bytes()).decode()
s = (root / 'carousel.src.html').read_text()
for k in ('B', 'UD', 'OS'): s = s.replace(f'%%{k}%%', paths[k])
s = s.replace('%%COVER%%', cover).replace('%%QA10%%', qa10)
(root / 'carousel.html').write_text(s)
print('carousel.html', len(s))
