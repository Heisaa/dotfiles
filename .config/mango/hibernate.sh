#!/bin/sh
# Leave the hibernate key mode first, so mango isn't still in it after resume.
mmsg dispatch setkeymode,default
exec systemctl hibernate
