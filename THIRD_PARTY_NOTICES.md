# 第三者ライセンスに関する通知

この文書は、`requirements.txt`に記載された直接依存関係を確認するためのinventoryです。ライセンス本文を代替するものでも、法的判断を示すものでもありません。実際に配布するartifactでは、解決された正確なversion、transitive dependency、base imageに含まれるsoftwareを別途確認してください。

| 直接依存関係 | 使用条件 | 参照先 | 確認状況 |
| --- | --- | --- | --- |
| PyYAML (`PyYAML>=6.0.3`) | YAML設定の読み書き | [PyPI](https://pypi.org/project/PyYAML/) / [upstream LICENSE](https://github.com/yaml/pyyaml/blob/main/LICENSE) | upstreamはMIT Licenseを掲示しています。公開artifactで採用されるversionのmetadataと同梱LICENSEを要確認 |
| tomli (`tomli>=2.4.1`; Python 3.11未満のみ) | `tomllib`がないPythonでTOMLを読むcompatibility dependency | [PyPI](https://pypi.org/project/tomli/) / [upstream LICENSE](https://github.com/hukkin/tomli/blob/master/LICENSE) | upstreamはMIT Licenseを掲示しています。条件付き依存のため、対象Pythonと採用versionのmetadata・同梱LICENSEを要確認 |

## Containerと間接依存関係

`Dockerfile`は`python:3.12-slim`をbase imageとして利用し、build時に`bash`、`ca-certificates`、`git`とPython依存関係を導入します。これらにはMIT以外のライセンスも含まれます。base imageのdigest、OS package、Python packageはbuild時点で変わり得るため、この文書だけでは完全なSBOMまたはnoticeになりません。

release候補をbuildした時点で、少なくとも次を確認してください。

1. 解決されたPython packageとversion
2. containerに含まれるOS packageとライセンス情報
3. base imageのprovenanceと利用条件
4. 必要なcopyright notice、license text、source提供条件

依存関係やbase imageを更新した場合は、このinventoryも更新してください。
