# Task 5A aesthetic scene correction report

## Status

Complete. The four completion-authoritative Task 3/4 editorial scenes were corrected, exercised through three complete native-pixel Cycles scout rounds plus focused gobo probes, archived byte-for-byte before replacement, republished under marker-last authority, and fresh-reopened in Blender 5.2. Task 5 code and Shopify/theme files were not modified or invoked.

## Repository changes

- `scripts/blender/pimm_production/editorial_sets.py`
  - Rebuilt each concept's scene-local light rig at the millimetre-scale energies required by the linked product.
  - Added governed world lifts, broad front/base fill, and correctly aimed area lights.
  - Replaced the architectural two-bar cross with a six-bar horizontal-plane grid and kept it left of the product.
  - Lifted the graphite floor/wall while retaining the dark-engineering palette.
  - Removed the still-life foreground blocks that controlled the portrait framing.
- `scripts/blender/pimm_production/blender_editorial_scene.py`
  - Added exact per-concept composition policy for procedural scale/gap, external placement, framing eligibility, gobo placement, and camera safety.
  - Moved the full-scale workshop cart laterally and deeper; moved the toolbox behind the process machine; excluded both from the camera solve.
  - Tightened workshop/process coverage safeguards.
  - Rebuilt the contact receiver as one upward-facing quad. The old collapsed cube left coincident faces that rendered the nominal floor black.
- `scripts/blender/pimm_production/tests/test_editorial_sets.py`
- `scripts/blender/pimm_production/tests/test_blender_editorial_scene.py`
  - Added regression coverage for the exact corrective light, world, gobo, composition, coverage, and contact-receiver policies.

No source master, material library, foot patch, CC0 file, external-asset manifest, Task 5 renderer, or theme file was modified.

## TDD evidence

The corrective tests were introduced before their implementations.

- Initial RED caught the previous low-energy/un-aimed rigs, the two-object gobo, absent composition policy, undersized workshop/process coverage policies, framing-eligible context, and missing broad base fills.
- A second RED caught the insufficient dark-rig scale, incomplete composition values, and the contact receiver still retaining collapsed box topology.
- A final gobo-specific RED caught the old vertical cross geometry/placement rather than a recognizable grid.
- Each RED was followed by the smallest corresponding implementation and a GREEN focused run. The final focused run is recorded in Validation.

## Rejected baseline

Rejected Task 5 generation:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\proofs\editorial-concepts-v1\rejected\editorial-preview-20260830T074446.532746Z-267afa77-9355bc33`

The four PNGs and contact sheet were inspected at native pixels before editing. The values below come from that generation's `campaign-report.json`; `clipped-dark` is the Task 5 report field.

| Concept | Full mean | Clipped-dark | Machine area | Machine height | Rejected PNG SHA-256 | Native-pixel verdict |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Architectural daylight | 83.012198 | 0.285826823 | 0.2257238871 | 0.9259258993 | `127821D264DEBF4085CC62D23925043120FA9EF290B9EF47F99D148CC2476900` | Lower machine and feet merged into a black floor; no credible grid; AirTAC marginal. |
| Dark engineering | 1.186893 | 0.942365451 | 0.1967991863 | 0.9259258881 | `94E8DDBD7602B702850836C48868D7DAE7A7DAAB36733B57BF58501CD5AA3A08` | Near-black silhouette; controller, gauge, AirTAC, underside, and feet unreadable. |
| Modern workshop | 70.938087 | 0.297296007 | 0.1940656298 | 0.9194728620 | `E7E781EBB68F0CCE00A6896732D01E68AF7053A04EFD84C20F3261F58B391858` | Saturated green cart engulfed the machine; floor/base were crushed. |
| Process still life | 26.562934 | 0.408518519 | 0.0929259601 | 0.3985311985 | `7D84E4D64528A007B5620FF578B77F6DF66FBAB46FEF990F593CE99319E66C77` | Machine was small, props dominated, and the lower field/underside were unreadable. |

## Scout iteration

All scouts were real Blender 5.2 Cycles renders at the contracted native output dimensions, AgX / Medium High Contrast, f/11, and eight samples. Every image was inspected at native pixels. The ROI definition was projected axis-aligned world-bounds rectangles; feet metrics use the union of the four projected foot rectangles.

Scout root:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\proofs\editorial-concepts-v1\rejected\task-5a-scouts-20260830T000001Z`

### Round 1

| Concept | Full mean | Machine mean | Feet mean | <=5 fraction | Area | Height | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Architectural | 88.7365 | 78.6883 | 28.5068 | — | 0.225724 | 0.925926 | Failed visual review: black floor; no grid. |
| Dark | 6.7823 | 18.3394 | 11.8624 | 0.731180 | 0.196799 | 0.925926 | Failed quantitative and visual gates. |
| Workshop | 79.2002 | 78.7579 | 25.9776 | — | 0.196799 | 0.925926 | Cart dominated; black floor/base. |
| Process | 59.8998 | 64.2546 | 14.3633 | — | 0.196093 | 0.578928 | Product/feet too small; toolbox dominated. |

Diagnosis from the pixels and scene topology: area-light wattages were effectively tiny for a millimetre scene; several nominal fills faced away; the contact receiver was a zero-thickness collapsed cube with overlapping faces; full-scale external context and wide process blocks controlled the camera solve.

### Round 2

| Concept | Full mean | Machine mean | Feet mean | <=5 fraction | Area | Height | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Architectural | 155.9860 | 137.3790 | 136.3130 | — | 0.225724 | 0.925926 | Lighting/floor passed; grid remained cropped/unconvincing. |
| Dark | 45.4937 | 64.6696 | 67.1303 | 0.001140 | 0.196799 | 0.925926 | Passed; readable graphite engineering mood. |
| Workshop | 105.1505 | 97.9155 | 58.1964 | — | 0.208205 | 0.952381 | Passed; cart reduced to peripheral context. |
| Process | 69.6373 | 67.1960 | 32.3159 | — | 0.501609 | 0.925926 | Passed; portrait product hero with edge context. |

Two additional architectural gobo probes were rendered. The first moved the original cross but produced an over-broad shadow; the second used a horizontal-plane grid and produced the readable off-product pattern carried into Round 3.

### Round 3, final policy

Directory:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\proofs\editorial-concepts-v1\rejected\task-5a-scouts-20260830T000001Z\round-03-final-policy`

| Concept | Full mean | Machine mean | Feet mean | Full <=5 | Area | Height | Safe margin | PNG SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Architectural | 153.830042 | 134.449593 | 80.736413 | 0.000808377 | 0.2257238871 | 0.9259258993 | 0.0370363705 | `423A8929DC7A3AF0D9C52CC9D506560F0AA13AA8F8552BE6EBF98C33C57E202B` |
| Dark | 45.493671 | 64.669577 | 67.130275 | 0.001140408 | 0.1967991863 | 0.9259258881 | 0.0370359644 | `F41D4891E44B34C918B5797D66C8A372E59911B4FAB88AE9687737D27732BA57` |
| Workshop | 105.150456 | 97.915462 | 58.196370 | 0.006148003 | 0.2082054986 | 0.9523809664 | 0.0238088258 | `641C7C9FF23C7C651C609FE810BF9A60E5B7554B14658425C8D072A1C1279182` |
| Process | 69.637285 | 67.195969 | 32.315881 | 0.017762963 | 0.5016085952 | 0.9259258658 | 0.0370364040 | `3F97BAA2DC2541E0C7EE4100CAA5408651EE59ABCB485F9A2C8F9B59874E1DD6` |

No final scout contained luma >=254 pixels (`0.0` fraction for every full frame, machine ROI, and feet ROI).

### Visual self-review

- Architectural: warm floor and wall read as one continuous set; a clear multi-pane grid appears on the left without crossing the product; stainless surfaces, controller, gauge, AirTAC, base, and four feet remain readable.
- Dark: graphite mood remains distinct, with shaped warm key, cool bilateral rims, and visible front/base detail; the machine is not a silhouette and its gauge, AirTAC, underside, and feet resolve.
- Workshop: the cart is only a peripheral right-edge context sliver; the machine is the central and strongest contrast/detail mass; base, feet, gauge, and AirTAC resolve against the set.
- Process: the product fills the portrait frame while cropped tooling/pellets/drawing context stays at the edges; no product/designed-shadow clipping is visible; underside and feet remain separated from the floor.
- Across all four: no washed highlights, floating feet, accidental collision, foot occlusion, or third-party equipment branding was observed. The four concepts remain materially distinct.

## Archive before replacement

The then-current authoritative scene, contract, completion marker, and transaction journal for each shot were moved into this new rejected revision before any replacement was published:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scenes\rejected\pimm-editorial-concepts-v1\20260830T111742.9688128Z-task-5a-aesthetic-rejection`

All 16 archived files were rehashed after the move. Their byte lengths and SHA-256 values match the pre-move records.

| Concept | Artifact | Bytes | Archived SHA-256 |
| --- | --- | ---: | --- |
| Architectural | scene | 144781 | `77D5B62D6575622B46BD4A74A9F7CE9E05F172D8140EBE4C4A029FF6590DEC7E` |
| Architectural | contract | 4597 | `95ECBDC2B353B5D1B7B45526EF6FAE1C7F6D10E6672C9F5D538DB97D1829E683` |
| Architectural | marker | 1751 | `3A1D6876ECEC2C3CECF7906B57B145DA79D1D66FE01DFDA901D55810CBAC6C77` |
| Architectural | journal | 1749 | `B6E9FF0E7B42CB7EC0F4EA16AEBC881E77A3DC7FCC64DD0F2642632E7ABEF3B3` |
| Dark | scene | 144001 | `A32581786C686A2FCB2FB7EEF4E6004716E1D8D3B5DAA6B18195CE446736B738` |
| Dark | contract | 4319 | `7170AFFEBBA39AAF1DD6D80DEEA61717812D21834C2D7EB4F79ABD709F18D900` |
| Dark | marker | 1709 | `C83887EB3E2775E7F04C148A59A6B8E248472E22BDAD12F614545502C94C8CDF` |
| Dark | journal | 1707 | `CBD7DB2B18574D42B8EA3A5F8692678BF25CAB4E2BCF2C8764CD5A276F810717` |
| Workshop | scene | 236169 | `8EB5FB806567C1FF3DBEAAD2C5B25875F71B872466FBF2BC536F350951D4D1F0` |
| Workshop | contract | 23289 | `4107F3C9641F3B3C6A592D850F9C375829EFFF9E88C0DC949BA1DC979EC84C8A` |
| Workshop | marker | 1702 | `B20DC2D5F62E6C7C354ACAA82069F2E94A9DC80633F2A0CDEBC0AD1EB28151A3` |
| Workshop | journal | 1700 | `7EF38FD9308992816B002AC867F866DCA3110FCD59FAA5F8C296FA1FA84B4BC3` |
| Process | scene | 274315 | `4DAB7180767A0D2F55DC81FEEDBFEBE92E1620598AC474C4A1BADECF159F41C8` |
| Process | contract | 30355 | `40885921FEC0A45CDDD60321FABA6801670DA674EA262C99205CA167BADBB3F9` |
| Process | marker | 1723 | `62E29FCB5EAC46F7D69AA3DDA75E7D4AD24AE977B6391E8A5CB2C8545115683E` |
| Process | journal | 1721 | `DDA47AFD480DD44A61C842B23742C8674345CE94E740E726FE1949F7E9F0BA71` |

Archived transaction IDs were `18251d5092644166965ce55ba4d87335`, `96b465405c46498390c7492a3cd30efd`, `038dd21920ce4d08842c3cedfa6305b1`, and `0d75cf6fc5c74b5c9b0be05b7e643ff0` for architectural, dark, workshop, and process respectively.

## Corrected authoritative publication

Each corrected scene was authored from Blender 5.2 factory startup and returned `published_preview_scene`, `fresh_validation=true`, no validation errors, and protected-input hashes unchanged before/after. Marker-last publication is complete; fresh snapshot readback reports scene hash, contract hash, and transaction ID all matching.

| Concept | Transaction | Scene SHA-256 | Contract SHA-256 | Marker SHA-256 | Journal SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Architectural | `a0317085804f4381925d74d39dcd8b41` | `926621C03C2387744E3602C330A33A0EEDC2B3590EEA60F116399CC89932BF33` | `73BD7B94A8360BFBB1D21C18CB1A027B69C3778F2514F083F2653D8770AAB80B` | `2B04C9B9496A8FA1B368FB3308A41F0430F46A5397777272061CBBD45E284A1E` | `4188201597962505D6D9587F0B9BD0BB41A0EA0008B26A952DA4F8A5E533E72E` |
| Dark | `1a5251d268ad4fc79c3137e991ec00e2` | `CE85B57C34CB5F165FE62DC6B402963C3071F1CC20A89AA905F4248F23C212DB` | `929C720B1F54AC34AF0070E0C9BDF4D0A485E3D846C99D18FCA76E0B78E440BA` | `6F73D38AD8A493372C4CB3FB0713C8D02387B87175816D99C357C45C4C9096F4` | `C4BBC568BD5AF59CCC6DEFD9718F263951B0F31E8DCCF455B0FE6365D7ACCAAB` |
| Workshop | `08a33dc94000478ba02e88bd6311b1f5` | `73D5D5FEF042B602626CA0771EC666D575FF1A467E93F8B5CF20F91DC1680EB3` | `C755C2709E8B2AEB16B9D288DA2C859198D8AD7CB7EFACE3E0A77629FB8FEAAF` | `5094408799612669F32CEF4AD78E489805361740177EE401316EA95B760F4FD1` | `4B5730B058649AACB606D36B3EE92C44D5273DD4BC17ED082BC0B75A45953070` |
| Process | `d073e4521f4c4b79b188641454b7c987` | `8483A0444A06BE6D80BEFAAC6B6E6EB18CE06E4E65ACE11C5065DB2476FFEFAD` | `C02023A16F7385407A9656DD0B6B305E5EF2F59397D9F91B0BA1747B5BDBEFF9` | `F2E4C1A57E253F186889444AFF5017974407008D4D5732D40E081251A84BAE10` | `2369973E52D11D5DA845D43EDCDB38B072624D881F883892B2A9C51CCC4D34A4` |

## Contract, contact, framing, and identity evidence

| Concept | Focal / dimensions | Area / height / safe margin | Geometry / light signatures | Reopened scene geometry / light signatures |
| --- | --- | --- | --- | --- |
| Architectural | 85 mm / 1280x720 | 0.2257238871 / 0.9259258993 / 0.0370363705 | `D797E4433078065206E806CD2F31921D5AF1A2F899FC9276B6A86B28B96B4ABF` / `6AB82E7B7D396F2E75491EC30F8FD18AC0A0D84F90838D1F44BD42AF55502E85` | `70BBF5E0ED586F609526A58674C811868868163FB2D249D61A73E062C3779F02` / `96E27E73B0039D7B01A4E65CD0F3F0B7251E306EA1AA598B823C55795D2A7B54` |
| Dark | 135 mm / 1280x720 | 0.1967991863 / 0.9259258881 / 0.0370359644 | `6A842799BC511B809155B1D3A1142320767F5B202EF786CC03945FA3B38679CD` / `7958547C84E47BDC37B43DD665409F93608FAE693D90CD65DD020D32963A1D9F` | `BEC8A8A4031167243256ED9F7E1B5DAAFCA52D7A8F8192EA13AFE8CBC343011B` / `F5C29EBF4AA489889DECCC02D0271089156B4EC795504A4A4E2667F8DAA3776E` |
| Workshop | 85 mm / 1280x720 | 0.2082054986 / 0.9523809664 / 0.0238088258 | `55DDDB2FDA017A412CA68B35AAEF363C13C03C8B5AD1B22CD0BE5D74E438D46D` / `3B7A14FFE66918EECFA9FC53AC56DF23F0F49C09148581C8DF095EFAAF08A74B` | `A624812755A319F6D4BA4377D382B8A86789684C19A0DE06951B6FBB5B26B036` / `D04821D5471A6A7A71A5B3023E377055FFBBB33C1D43EC25133695E8F1CA2B5B` |
| Process | 180 mm / 900x1125 | 0.5016085952 / 0.9259258658 / 0.0370364040 | `08B531DD8C566385A3E2B5F88504B503CEC58E34D960D69041C35DB368209B34` / `5EA84A1B7142C1DDCFD13F9997116F840CDE027419C77F4FE7169AB1DEC79554` | `E040F3AC15D5FDAA4CD647A0032158406C7D88909CA41D24435ACCFF0F3408A8` / `95896DEC1FC508C52AA46BF20AA0D806637530513621F4EE19951E330848589B` |

Every scene preserves f/11, 36 mm sensor, Cycles, 32 authored preview samples, denoising, AgX, `AgX - Medium High Contrast`, `preview_only=true`, and `final_authorized=false`.

Fresh Blender snapshot evidence for every shot:

- Exactly 554 linked product objects; no local product copy.
- 30G stable-ID SHA-256: `5F728131467B2186D7DA6E7084B85F96278C12D16995BC6C511A004685A4BF77`.
- 50G stable-ID SHA-256: `83B6588AA7B8C31C99DAEA39ACC1FBBC523C0A0BBFA1B518841A0CFE42F7ED5B`.
- One contact plane covers all four feet. Contact Z is `-1.1160036592627876e-06`; spread is `9.35423668124713e-06`, below the `0.0002` tolerance; outlier list is empty.
- 30G foot IDs: `30G-64039c77f719dbec`, `30G-1a7f1009f15a7ee4`, `30G-7419ee7fe262373b`, `30G-d81608e985bd200f`.
- 50G foot IDs: `50G-4ba184a5ab1f9699`, `50G-128eb11d742a1eb0`, `50G-52ed17bc40830918`, `50G-4513ee4e5dd3ae2c`.
- Support/machine intersections: none. Supports hiding feet: none. Complete-machine framing: true.

## External provenance

Fresh readback matches the manifest and linked libraries exactly; `machine_master_modified=false` throughout.

| Asset | Version ID | License | SHA-256 |
| --- | --- | --- | --- |
| `university_workshop` | `university_workshop:hdris:4k:exr:ed5349382a8d04177f1af0e622baef18` | CC0-1.0 | `DB140B5BD170C533803E6782B02077482C1B3EECB6981821AA8414F240BB4760` |
| `tool_cart` | `tool_cart:models:1k:blend:3861700017732faa0f596ee072647726` | CC0-1.0 | `52F4A580757E183DDEEED1FE18577E27A69A71D5BBDEB640C65DAFB2EF67AC4B` |
| `metal_toolbox` | `metal_toolbox:models:1k:blend:e0ea9770745ba209029fecc482e27d53` | CC0-1.0 | `37E1528121DF301E5E34C00682639C5BA81C5AA90D1FD1894CC86486946E680C` |

## Protected-input hashes

These were checked before/after each corrected author operation and rehashed again after publication.

| Protected input | SHA-256 |
| --- | --- |
| `masters/PIMM-30G-MASTER.blend` | `98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA` |
| `masters/PIMM-50G-MASTER.blend` | `20F041F42678EE6E1A789018761D1FDE28AABD713936F6D951E09D183F333A12` |
| `masters/PIMM-MATERIAL-LIBRARY.blend` | `F511A97A32CEA33B633CCE852FA04A4999663C64F41A3E69151923C862AD2F1B` |
| `manifests/patches/PIMM-30G-foot-refresh.json` | `118CAED48AA1495C339158DC71C94F84142B84E31097407201C39EBF032D055D` |
| `manifests/patches/PIMM-50G-foot-refresh.json` | `E362247D8990D348D5AA49A326793FF7F2EFCE33BC79175DC507DAB13EA8FD3F` |
| `manifests/external-assets-v1.json` | `3D7964E7A06BB10815F3986799981D6008322830E00ADA2C8B0FE397262EC5F4` |
| University workshop EXR | `DB140B5BD170C533803E6782B02077482C1B3EECB6981821AA8414F240BB4760` |
| Tool cart Blend | `52F4A580757E183DDEEED1FE18577E27A69A71D5BBDEB640C65DAFB2EF67AC4B` |
| Metal toolbox Blend | `37E1528121DF301E5E34C00682639C5BA81C5AA90D1FD1894CC86486946E680C` |

## Validation

- Focused Task 3/4 tests:
  - `python -m unittest scripts.blender.pimm_production.tests.test_editorial_sets scripts.blender.pimm_production.tests.test_blender_editorial_scene -v`
  - Result: 49 tests, all passed. This includes a real Blender 5.2 reopen/signature mutation test.
- Adjacent campaign/asset tests:
  - `python -m unittest scripts.blender.pimm_production.tests.test_editorial_concept_contract scripts.blender.pimm_production.tests.test_campaign_contract scripts.blender.pimm_production.tests.test_external_asset_manifest scripts.blender.pimm_production.tests.test_polyhaven_assets -v`
  - Result: 31 tests, all passed.
- Compile check:
  - `python -m compileall scripts/blender/pimm_production`
  - Result: exit 0.
- Fresh scene validation:
  - Every authoritative `.blend` was reopened against its authoritative contract with Blender 5.2; each returned `PIMM_EDITORIAL_VALIDATION_JSON=[]`.
  - A subsequent single-process `--factory-startup` snapshot reopened all four scenes and exited 0. Every shot returned `errors: []`, publication complete/hash-matched, exact camera/render settings, valid linked identity/contact, and no collision/foot occlusion.
- Repository hygiene:
  - `git diff --check`: clean before report authoring; rerun before commit.

## Concerns and deliberately excluded work

- The final process scout feet ROI mean is 32.315881, above the 30 minimum but with less headroom than the other concepts. Native inspection still shows all four feet and the underside separated; the authoritative scene is configured for 32 samples versus the eight-sample scout.
- Blender 5.2 emits deprecation warnings that `Material.use_nodes`, light `use_nodes`, and `World.use_nodes` are expected to be removed in Blender 6.0. Validation returned no errors; Blender 6 migration is outside Task 5A.
- No fresh Task 5 campaign preview was generated because Task 5 renderer/theme is explicitly outside this correction lane.
- No native final render, Shopify publication, push, or deployment was performed.
