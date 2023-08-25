# heinlein

`heinlein` is a high-level tool for interacting with local versions of astronomical survey datasets. `heinlein` empowers astronomers who work with large survey datasets to stop thinking about files and start thinking about astronomy. Let's say you had downloaded some catalogs from the Dark Energy Survey. You could add these catalogs to heinlein with a single command:

`> heinlein add hsc catalog /path/to/catalogs`

Once this is done retrieving data in a python script becomes a simple as: 

```
from heinlein import load dataset
import astropy.units as u

des = load_dataset("des")
catalog = data.cone_search(center=(141.23246, 2.32358), radius=120*u.arcsec)
#Returns a standard astropy table
```

`heinlein` understands that it's pointless to load an entire dataset when you only need one small piece of it, so it contains tools to intelligently portions of the data based on what's needed at the moment. You can easily setup your previously-downloaded catalogs to work with these features by calling:

`> heinlein split des /path/to/catalogs`

`heinlein` also knows that if you're getting data from one part of the sky, there's a decent chance you'll come back and try to get data from a nearby part of the sky. `heinlein` caches data so queries nearby a perviously-queried area will return substantially faster.

But `heinlein` doesn't only work with catalogs. For analyses that rely on photometry, it can be necesary to remove objects from a catalog that fall within a mask provided by the survey team (often because of a nearby bright star). It's easy to use `heinlein` to manage these masks and apply them to catalogs:

```
des = load_dataset("des")
data = data.cone_search(center=(141.23246, 2.32358), radius=120*u.arcsec, dtypes=["catalg", "mask"])
catalog = data["catalog"]
mask = data["mask"]
masked_catalog = catalog[mask]
```

`heinlein` will happily keep track of any data you give it, but it only contains built-in tools for certain datatypes (currently catalogs and masks). 

**Currently supported surveys:**
DES, HSC SSP, CFHTLS

**Data types with built-in utilities:**
Catalogs (plaintext (csv, tsv etc), sqlite)
Masks (.fits, .reg, mangle)

Interested in adding something to these lists? Don't hesitate to add it in "Issues."
