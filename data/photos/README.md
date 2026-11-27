# Place photos

Photos of campus buildings taken by the team, shown in the app's place card ("Place in your
question"). Use your own photos only (the repository is public).

1. Save the photo here, for example `data/photos/ib.jpg` (landscape, about 1200 px wide is enough).
2. Add a row to `data/place_photos.csv`: `place_id` is the `id` column of `data/buildings.csv`,
   `file` is the path from the project folder, `credit` is shown under the photo.

```
place_id,file,credit
ib,data/photos/ib.jpg,"Photo: team, Nov 2026"
```
