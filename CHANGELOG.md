<!-- markdownlint-disable -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-02-25

### <!-- 0 -->Features
- Added support for echart graph (force directed node graph) and tree  by @marcelo-6 ([079bab4](https://github.com/marcelo-6/controls-workbench/commit/079bab4ba9a4c7e842a0349c877b38a6828f0cdf))

- Added echarts tree/chart creation and refactor index code into analyis for more flexibility  by @marcelo-6 ([f54f573](https://github.com/marcelo-6/controls-workbench/commit/f54f57321d313e9f34d5a3cf5c96f2026a6e39ac))

- Better project tree  by @marcelo-6 ([a9f1633](https://github.com/marcelo-6/controls-workbench/commit/a9f16339a2a79ff23dca2503641fb3c7ccb4b81c))

- Added files to metadata field of graphnode when we parse the igntion project  by @marcelo-6 ([b1ebb77](https://github.com/marcelo-6/controls-workbench/commit/b1ebb776be3f9e3aaf47fc0f7185271f1c60ff1f))

- Nodes can be dragged now, but it feels slow, maybe its the thumbnail rendering  by @marcelo-6 ([f4c7828](https://github.com/marcelo-6/controls-workbench/commit/f4c78284e9abfabe0fe13b4e68e45bc68f756e30))

- Much better auto layout and zoom in/out  by @marcelo-6 ([a854bde](https://github.com/marcelo-6/controls-workbench/commit/a854bdec21d2826bca76b6b8019cf5da8f850aa4))

- Python 3.14  by @marcelo-6 ([c352d1c](https://github.com/marcelo-6/controls-workbench/commit/c352d1c868d6fe7be7591c65c4f772525c03ff31))

- Added npm for pre-release macro  by @marcelo-6 ([3681a6b](https://github.com/marcelo-6/controls-workbench/commit/3681a6ba109bdee8dc3b2a3ae13459efb045393d))

- Project upload left panel now retractable  by @marcelo-6 ([161f9cb](https://github.com/marcelo-6/controls-workbench/commit/161f9cb56452f31aa678bbada365aafa65dff9fe))

- Added version indication to ui and backend  by @marcelo-6 ([0c374b9](https://github.com/marcelo-6/controls-workbench/commit/0c374b9c39566504cf1c8b19e0717c9977eb60fe))

- Improved status chip  by @marcelo-6 ([88dd9e0](https://github.com/marcelo-6/controls-workbench/commit/88dd9e0d55010aca0f861c76659eba2774c67b9a))

- Side bar starts collapsed  by @marcelo-6 ([22d68ad](https://github.com/marcelo-6/controls-workbench/commit/22d68ad1b71b9dcf712eafa28927ee75926c9e87))

- Added auto fit when graph is changed  by @marcelo-6 ([520d918](https://github.com/marcelo-6/controls-workbench/commit/520d91817298d7b7483e4e9df4a07a62aa1b0c1c))

- Added remove/delete endpoints to clear run history  by @marcelo-6 ([8a1b099](https://github.com/marcelo-6/controls-workbench/commit/8a1b09964b64d931226a5f789e38ac828654a1a7))

- Add sqlite catalog for run history + ignition graph index  by @marcelo-6 ([27d95cb](https://github.com/marcelo-6/controls-workbench/commit/27d95cbf1006997754529249bee372ddc311b32d))

- Added option to docker compose up only backend services (api and worker)  by @marcelo-6 ([060ddc9](https://github.com/marcelo-6/controls-workbench/commit/060ddc9a43b7fe21620b7fed8f375cb3f57a611f))

- Added theme toggle and adjusted theme for react flow graph  by @marcelo-6 ([8e76ecc](https://github.com/marcelo-6/controls-workbench/commit/8e76ecccd6acf29b6428667774d6a3559ec67414))

- Added release makefile recipe  by @marcelo-6 ([7d6abfb](https://github.com/marcelo-6/controls-workbench/commit/7d6abfb42a26e58c630c2920c8da6b9e8f314680))

- Add precommit hooks and fixes lint failures  by @marcelo-6 ([cec5f37](https://github.com/marcelo-6/controls-workbench/commit/cec5f376241f19231e971e2c2223fae1141ed565))

- Initial commit  by @marcelo-6 ([c9b97d3](https://github.com/marcelo-6/controls-workbench/commit/c9b97d3d07708f2abc8a492469ede25db74503ae))


### <!-- 1 -->Bug Fixes
- Graphs properly render and only ONCE!  by @marcelo-6 ([5cb22fd](https://github.com/marcelo-6/controls-workbench/commit/5cb22fdfaac81c6a344cdf07773968f72d7019f0))

- The render keeps clearing the state that we hold the tree and graph on...  by @marcelo-6 ([a46389f](https://github.com/marcelo-6/controls-workbench/commit/a46389f612a85d2274d679c18bf4e2bcfbf72f98))

- Some frontend improvements but mostly trying to get react flow graph to generate  by @marcelo-6 ([653f4d6](https://github.com/marcelo-6/controls-workbench/commit/653f4d640d98ef910f07fc70c2e85c981d6513f9))

- Fixing things before new version  by @marcelo-6 ([884ec28](https://github.com/marcelo-6/controls-workbench/commit/884ec2862d439549082e4d51052804bd104fa452))

- Fixed the queue worker not picking up tasks  by @marcelo-6 ([9cfe204](https://github.com/marcelo-6/controls-workbench/commit/9cfe20402b881891224e97c131c4b3cf6e63d0a9))

- Upload endpoint returns as expected  by @marcelo-6 ([e89228c](https://github.com/marcelo-6/controls-workbench/commit/e89228c9ebe229e7ff3e7af58ff696af0566489f))

- Fixed some issues with routes  by @marcelo-6 ([579a076](https://github.com/marcelo-6/controls-workbench/commit/579a076103d77350c13cc16eca38133a5918c30d))

- Fixed some huey issues and docker files because of the big refactor  by @marcelo-6 ([ecca86a](https://github.com/marcelo-6/controls-workbench/commit/ecca86a0784725977f58f262be6e52682e31bb15))

- Fixed theme for topbar  by @marcelo-6 ([c444bd3](https://github.com/marcelo-6/controls-workbench/commit/c444bd3cbeece4427fd5d2bef7b8837e2b530ecc))

- Fixed overflow issues on lists and added backend api page link  by @marcelo-6 ([ae772e5](https://github.com/marcelo-6/controls-workbench/commit/ae772e53079caf161f05d2dd195bbe2e18301147))

- Added linting and format options to makefile  by @marcelo-6 ([45bbeed](https://github.com/marcelo-6/controls-workbench/commit/45bbeed01e70c03be7457e3fcce7304061002c8a))

- Make zip now zips only what git tracks  by @marcelo-6 ([f7f6bb9](https://github.com/marcelo-6/controls-workbench/commit/f7f6bb96becc7a2d45e1838091b8506af1a551b6))

- Added docker build commands to makefile  by @marcelo-6 ([4802cc8](https://github.com/marcelo-6/controls-workbench/commit/4802cc8d736dbcd806ec99fabe97bf9690fc427d))

- Added better styling  by @marcelo-6 ([47d1f7e](https://github.com/marcelo-6/controls-workbench/commit/47d1f7eec68b4d46beb23026f86c78cfecd5eff7))

- Improved makefile macro outputs  by @marcelo-6 ([21f3021](https://github.com/marcelo-6/controls-workbench/commit/21f30213366bcf62d3a311b6f34424ea67feb79a))

- Added a check to verify version numbers changed in pyproject and packages.json  by @marcelo-6 ([156977f](https://github.com/marcelo-6/controls-workbench/commit/156977feba0839f0730f99f8e7236282a3c25b19))

- Added better tools check to makefile recipe  by @marcelo-6 ([255b474](https://github.com/marcelo-6/controls-workbench/commit/255b474246f7cf43bab908b985916fd7f07753fb))

- Makefile improvements  by @marcelo-6 ([d8f3a05](https://github.com/marcelo-6/controls-workbench/commit/d8f3a058f69eb6d0f0dbb0e6820c0512600f8a3b))

- Make file release no edit in amend  by @marcelo-6 ([d793a71](https://github.com/marcelo-6/controls-workbench/commit/d793a7117e3c1ca89e0af134a212d604b8d71f13))

- Makefile release recipe order changed to tags -> changelog -> commit amend  by @marcelo-6 ([d672ad4](https://github.com/marcelo-6/controls-workbench/commit/d672ad45e5c1133e1970e5cae5de25e5a9d7dc70))

- Removed extra amend comment on makefile release recipe  by @marcelo-6 ([e3b2bae](https://github.com/marcelo-6/controls-workbench/commit/e3b2bae9bba218a3d86627c84dc63a6c77144e25))

- Fixed run history storage  by @marcelo-6 ([323628f](https://github.com/marcelo-6/controls-workbench/commit/323628f9e3bf58f66db20dedbaabc02a475aed5c))

- Added docker dev/prod distinction along with some parsing fixes  by @marcelo-6 ([bf3aa2e](https://github.com/marcelo-6/controls-workbench/commit/bf3aa2e4717da46fccb721eb8de57708075cdd90))


### <!-- 2 -->Refactor
- Removed old code  by @marcelo-6 ([c68cded](https://github.com/marcelo-6/controls-workbench/commit/c68cdeddfac736abf5ee2b99397bab0a2444f33b))

- IGN project explorer refactor  by @marcelo-6 ([a1ae191](https://github.com/marcelo-6/controls-workbench/commit/a1ae19140c52487b8a662493089d542620c12028))

- Moved all api routes and models to a better folder structure  by @marcelo-6 ([45886ef](https://github.com/marcelo-6/controls-workbench/commit/45886efbe5101db7f21374e911fc4bde490f220c))

- Moved queue and it is now more unit testable  by @marcelo-6 ([11709cf](https://github.com/marcelo-6/controls-workbench/commit/11709cf62bd2c61685ae1370e4984d7e506fdcd6))

- Big move of all domain and infra db into a more modular and easier to do unit tests. also added unit tests for them  by @marcelo-6 ([2578159](https://github.com/marcelo-6/controls-workbench/commit/25781591979abab0b7283c414678aa95aeea9b28))

- Moved file system operations and related to their specific folders and added pytest-cov with unit tests  by @marcelo-6 ([60c1ba0](https://github.com/marcelo-6/controls-workbench/commit/60c1ba003ea5feb80b7b0c0ab403c96847755298))

- Moved and created relevant db infrastructure code  by @marcelo-6 ([1981802](https://github.com/marcelo-6/controls-workbench/commit/198180224e6ecd736b736b7c0e11d526aaf87a53))

- Moved errors, logging, core api responses, settings to core module  by @marcelo-6 ([860e18b](https://github.com/marcelo-6/controls-workbench/commit/860e18b189f877a9080512f451feeb3007b88081))

- Moved settings to a central location  by @marcelo-6 ([ac70eec](https://github.com/marcelo-6/controls-workbench/commit/ac70eec8d7fa3b67c2835670be7a6dc8de0539ba))


### <!-- 3 -->Documentation
- Added demo gif  by @marcelo-6 ([a0c2813](https://github.com/marcelo-6/controls-workbench/commit/a0c281371cae723b7d163c50695cc2259e576273))

- Added design docs  by @marcelo-6 ([658439b](https://github.com/marcelo-6/controls-workbench/commit/658439b03eed1f2eac2c67b91da58028ed3ae3bc))


### <!-- 6 -->Testing
- Added better tests for IGN tool parser  by @marcelo-6 ([2dd2c9d](https://github.com/marcelo-6/controls-workbench/commit/2dd2c9d069311bc7a7757b860596108a52feda2f))


### <!-- 7 -->Miscellaneous Tasks
- Filter by non conventional commits and reset tags  by @marcelo-6 ([cfdc057](https://github.com/marcelo-6/controls-workbench/commit/cfdc0576f8cd39c35e3da0a1f92558e2492b1a79))


### New Contributors
* @marcelo-6 made their first contribution

