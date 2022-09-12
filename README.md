# heinlein

heinlein is a high-level tool for interacting with local versions of astronomical survey datasets.

Astronomy has a data problem. Or it has the opposite of a problem, depending on how you look at it. Recent sky surveys have returned a wealth of data, with billions of objects over hundreds (or thousands) of square degrees of sky. Often, the datasets are made publicly available for anyone interested in astronomy to access.

However once these datasets have been downloaded, working with them becomes a real challenge. Analyses of any amount of astronomical data requires significant amounts of boilerplate code to read and manage the data. This code can easily become more and more complicated as the datasets involved get larger and large.

`heinlein` serves as a high-level to astronomical datasets both large and small that allows the user to stop thinking about files and start focusing on science. 

For large surveys, heinlein wittles this boilerplate code down to a few lines. For example, suppose I had downloaded some catalogs from the Dark Energy Survey. I can point heinlein to the catalogs easily:

```
> heinlein add des catalog /path/to/catalog
```

If the catalog (or catalogs) cover a large region, you can make use of built in optimizations by splitting the dataset into subregions, which `hienlein` will intelligently load as needed:

```
> heinlein split des /path/to/catalog
```

Now at any time, I can load objects from a particular location within the DES footprint, provided it is included in the catalog I downloaded.

```
from heinlein import load_dataset
import astropy.units as u

des = load_dataset("des")
des.cone_search((13.4349, -20.2091), radius=4*u.arcmin)
```

This code return an Astropy table of all objects in the DES Catalog in a manner of seconds. For analyses involving iteration over regions, `heinlein` caches results so further queries near an already-queried region will be returned signifcantly faster.

However `heinlein` also works with much smaller pieces of data. For example, suppose you had some fits image you plan to use later. We can store it easily just as before.

```
> heinlein add MyProject image /path/to/image.fits
```

And then load it up at any time using

```
from heinlein import get_path
path = get_path("MyProject", "image")
```

However for many data types, `heinlein` understands how to load them already, so you could use

```
from heinlein import get_data
data = get_data("MyProject", "image")
```

which would return an Astropy HDUList.

## Installation

The best way to install `heinlein` is with pip:

```
pip install heinlein
```

## Roadmap

TBD
