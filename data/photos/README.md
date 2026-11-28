# Place photos

Photos of campus buildings taken by the team, shown in the app's place card ("Place in your
question"). Use your own photos only (the repository is public).

1. Save the photo here, for example `data/photos/ib.jpg` (portrait or landscape, about 900 × 1200 px is enough;
   save it again without the phone's location metadata).
2. Add a row to `data/place_photos.csv`: `place_id` is the `id` column of `data/buildings.csv`,
   `file` is the path from the project folder, `credit` is shown under the photo.

```
place_id,file,credit
ib,data/photos/ib.jpg,"Photo: team, Nov 2026"
```

Photos so far (taken by the team, Nov 2026): AD, IB, Library, E1, 2nd Student Dormitory,
Haoyang Experimental Building, EE.
