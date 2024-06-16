all:
	@echo "Targets:"
	@echo " clean"
	@echo " docs"
	@echo " docker"


clean:
	python setup.py clean
	make -C docs clean

.PHONY: docs

docs:
	$(MAKE) -C docs html

style-check:
	@(tools/style-format.sh \
		$$(git ls-tree -r --name-only HEAD | egrep '\.(c|h|py)$$') )

style-check-changed:
	@(tools/style-format.sh \
		$$( (git diff --name-only ; git diff --name-only --staged) | egrep '\.(c|h|py)$$'))

style-fix:
	@(tools/style-format.sh --fix \
		$$(git ls-tree -r --name-only HEAD | egrep '\.(c|h|py)$$'))

style-fix-changed:
	@(tools/style-format.sh --fix \
		$$( (git diff --name-only ; git diff --name-only --staged) | egrep '\.(c|h|py)$$'))

docker:
	docker build -f examples/docker/Dockerfile.alpine -t rhadi2005/confluent-client:latest .
	# docker push rhadi2005/confluent-client:latest
	@echo "Done!  Use 'docker run -it --rm rhadi2005/confluent-client:latest bash' to run"
