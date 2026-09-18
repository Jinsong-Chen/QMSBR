# Review-timing teaching data

`resource_timing.csv` contains 36 complete cases in the original order
of the archived teaching file `SPSS_2way.sav` (the 6020-25F26S
teaching archive). The donor columns were `Score`, `A`, and `B`.
The conversion preserves every score and both factor codes through
the labels below. Each of the nine cells contains four cases.

| Column | Meaning and coding |
|:--|:--|
| `student` | Sequential case identifier, 1–36; added during conversion. |
| `resource` | Original A: 1 = Textbook; 2 = Tutorial; 3 = Video. |
| `timing` | Original B: 1 = Same day; 2 = Two days; 3 = One week. |
| `score` | Original Score, unchanged; values observed in the file range from 7 to 20. In the invented setting, the 0–20 retention-quiz score counts correctly answered items. |

The Grade 7 setting, fractions lesson, learning-resource labels,
review times, quiz interpretation, and random assignment are invented
for Chapter 4. The generic archived file does not establish a real
educational study or document randomization.

In the stipulated design, 36 students in one school study the same
one-hour fractions lesson using a printed textbook chapter, an
interactive tutorial with immediate hints, or a recorded video lecture.
They review with the same resource on the same day, two days later,
or one week later. All take a 20-item retention quiz two weeks after
the lesson. Four students are randomly assigned to each of the nine
resource-by-timing combinations. The working ANOVA model assumes
independent students and common within-cell error variance; the exact
classical F reference additionally assumes Normal errors.

For an import check, the 36 scores sum to 407. The cell means in
resource order Textbook, Tutorial, Video and timing order Same day,
Two days, One week are (8.5000, 9.0000, 8.2500), (15.7500, 14.2500, 18.2500),
and (9.7500, 9.7500, 8.2500). The data contain no missing values.
