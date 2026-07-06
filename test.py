import jdatetime
import datetime

# Example input from your XML
gregorian_dt = datetime.datetime.strptime("2008-12-24 21:32:00", "%Y-%m-%d %H:%M:%S")

# Convert to Jalali
jalali_dt = jdatetime.datetime.fromgregorian(datetime=gregorian_dt)
print(jalali_dt.strftime("%d %B %Y"))