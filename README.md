# Justdial Dataset - Data Cleaning

Deleted duplicate row(s) using Excel.
Combined the Pice for Two and Rupees into One and deleted the rupees column. Filled the NaN values in this column with 00000.
Converted the People recently enquired column into a cloumn just havinh the number. Filled the NaN values with 0 implying 0 people enquired.
For the column having 'Order Online', 'Menu' and NaN values, 'Order online' had the highest value count, hence decided to convert into a column specifying whether Order online was available. So, the value 'Order Online' was replaced with 'Yes' and 'Menu' & NaN values was replaced with 'No'
There were two columns having the same contact information. So deleted one and cleaned the other. Replaced NaN values with 'Not Available'
Deleted the column having the same value 'more'.
The column having suggestion was deleted because of 70% NaN values.
The column having values like 'Clean Place' was decided becuase it had 70% NaN values.
5 columns having Ammnenities was combined into one column.
The column having '..Years in Business' was cleaned and NaN values were replaced with 'Not Available'.
Deleted the column having values like 'Open till .....' because I felt it didn't bring any meaning. Also, deleted column having values 'Open' for the same reason.
CLeaned the address column.
Cleaned the '..... Ratings' column
Dropped the columns having URLs. Didn't bring any meaningful info.
Cleaned the column having values like 'Trending'. Imputed NaN values with 'Not Available'.
Converted the column having values 'This business Information is verified by Justdial.' into boolean column.
