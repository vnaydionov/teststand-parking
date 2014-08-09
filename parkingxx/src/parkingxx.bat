@echo off
set PATH=c:\yborm\bin;%PATH%
set YBORM_URL=mysql+odbc://parking_user:parking_pwd@parking_db
parkingxx.exe
pause
