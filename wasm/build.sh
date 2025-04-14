cd ./packages/dfs_webworker
python -m build 
cp dist/*.whl ../../../frontend/public/

cd ..

cd promptopt

python -m build

cp dist/*.whl ../../../frontend/public/

cd ../..

