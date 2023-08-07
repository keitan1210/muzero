import os
version_path=os.path.join(os.path.dirname(__file__),"../srl/version.py")
exec(open(version_path).read())
project="SimpleDistributedRL"
copyright="2022,poco_cpp"
author="poco_cpp"
release=VERSION
extensions=[]
templates_path=["_templates"]
exclude_patterns=["_build","Thumbs.db",".DS_Store"]
language="ja"
html_theme="sphinx_rtd_theme"
html_static_path=["_static"]
