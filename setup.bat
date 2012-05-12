@echo off
FOR /F "tokens=1-4 delims=/ " %%I IN ('DATE /t') DO SET thedate=%%L%%K%%J
set app_name=drotrim
set zippath=C:\Apps\Misc\7-Zip\7z.exe
set pythonpath=C:\Apps\Programming\Python27\python.exe

rem --- Delete any existing artifacts ---
del %app_name%_bin_%thedate%.zip
del %app_name%_src_%thedate%.zip 

rem --- Package the binaries ---
cd src
%pythonpath% setup.py py2exe %1 --bundle 2
rd build /S /Q
rename dist %app_name%
mkdir ..\zip
move %app_name% ..\zip
cd ..\zip
mkdir %app_name%\docs
copy ..\docs\*.txt %app_name%\docs
rem bleh, I'm a big dummy and don't know how to do this in setup.py
copy ..\src\drotrim.ini %app_name%\

%zippath% a -tzip -mx9 -r -x!_bak -x!src ..\%app_name%_bin_%thedate%.zip %app_name%
cd ..
rd zip /s /q

rem --- Package the source ---
mkdir zip
mkdir zip\%app_name%
mkdir zip\%app_name%\src
mkdir zip\%app_name%\res
mkdir zip\%app_name%\docs
xcopy src zip\%app_name%\src /E /EXCLUDE:setup_src_exclusions.txt
copy *.bat zip\%app_name%\
copy *.ico zip\%app_name%\
copy setup_src_exclusions.txt zip\%app_name%\
xcopy docs\*.txt zip\%app_name%\docs
xcopy res\* zip\%app_name%\res

cd zip
%zippath% a -tzip -mx9 -r -x!_bak -x!.\src ..\%app_name%_src_%thedate%.zip %app_name%
cd ..
rd zip /s /q