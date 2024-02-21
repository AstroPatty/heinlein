import astropy.units as u

from heinlein import load_dataset

hsc_center = (141.23246, 2.32358)
radius = 120 * u.arcsecond


def test_hsc():
    print("TESTING HSC")
    d = load_dataset("hsc")
    a = d.cone_search(hsc_center, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    print(mask.mask(cat))
    print(a)


test_hsc()
