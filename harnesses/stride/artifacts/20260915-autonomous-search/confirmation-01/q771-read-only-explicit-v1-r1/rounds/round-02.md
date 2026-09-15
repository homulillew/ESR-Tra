# Round 2

[Actual request](../http/002/request.body) · [Actual response](../http/002/response.body) · [All interaction](../FULL_INTERACTION.md)

## Input visibility

```json
{
  "capacity": 30074,
  "compacted": false,
  "counter": {
    "calibrated_provider_tokens": false,
    "kind": "utf8_bytes"
  },
  "evidence_shelf": [],
  "final": false,
  "output_reservation": 4096,
  "request": "d396615dad514f7252d08fdd7919040e59747178315cdc9cfb8adf740c76d516",
  "round": 2,
  "shelf_evicted_for_capacity": [],
  "visible_documents": [
    "d1",
    "d2",
    "d3",
    "d4",
    "d5",
    "d6",
    "d7",
    "d8",
    "d9"
  ],
  "visible_evidence": [],
  "workflow_view": {
    "active_gap_not_verified": null,
    "available_pages_not_ranked_for_relevance": [
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d9"
        },
        "ref": "d9",
        "snippet": " ... Diversification\n\nIn the 1980s, Stetson began to diversify, releasing the first Stetson cologne in 1981 and Lady Stetson in 1986. Luggage, handbags, umbrell",
        "title": "https://en.wikipedia.org/wiki/Stetson"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d8"
        },
        "ref": "d8",
        "snippet": " ... So, with the advent of highways, there were even more cars and car travel occurring, and fewer people were traveling by train, subway, bus, or tram. So, th",
        "title": "https://www.gentlemansgazette.com/men-stop-wearing-hats/"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d7"
        },
        "ref": "d7",
        "snippet": " ... In interviews with the Irish press, he said he came to London because a poetry editor there had promised that, if he did, the editor would buy him a new tw",
        "title": "https://putthison.com/style-of-allen-ginsberg/"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d6"
        },
        "ref": "d6",
        "snippet": " ... File:Chakchai 2suit.jpg|Example of the two button slim-fit suit popular in the late 2000s in the UK, US and China.\nFile:CSD 2006 Cologne sexy 6.jpg|Woman w",
        "title": "https://en.wikipedia.org/wiki/2000s_in_fashion"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d5"
        },
        "ref": "d5",
        "snippet": " ... In order to bring New York fashion to Istanbul, Vakkorama introduced a new team called V2K Designers ('V2K Designers') in 2000 with the slogan \"Two cities,",
        "title": "https://en.wikipedia.org/wiki/Vakko"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d4"
        },
        "ref": "d4",
        "snippet": " ... Following a decline in sales due to the company's dusty image in the 1970s, Dumas rejuvenates the collections, brings new designers into the company, devel",
        "title": "https://wunderlabel.com/lab/fashion-company-histories/hermes/"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d3"
        },
        "ref": "d3",
        "snippet": " ... Under his reign, the medieval city was transformed into the Paris we know today, with grand boulevards, museums, and iconic structures like the Eiffel Towe",
        "title": "https://www.screwdowncrown.com/p/hermes-luxury-brand-history-birkin-kelly"
      },
      {
        "navigation_seen": true,
        "raw_ranges_delivered": [],
        "read_action": {
          "ref": "d2"
        },
        "ref": "d2",
        "snippet": " ... Hermès\n\nGetty Images\n\nWe started with a saddle shop and we'll end with a saddle shop. In 1837, Thierry Hermès opened a harness workshop for fine equestrian",
        "title": "https://www.mentalfloss.com/article/21572/real-people-behind-10-fashion-houses"
      }
    ],
    "consecutive_repeat_rounds": 0,
    "contract": {
      "enabled": true,
      "gap_state": true,
      "guided_read": true,
      "recovery_rounds": 2,
      "repeat_threshold": 2,
      "repetition": "bounded",
      "reuse_results": true,
      "version": "gap-workflow-v1"
    },
    "instruction": "Use the current missing relation to choose a real next action. Page-name search is not page reading; cached is not proof of progress.",
    "last_new_navigation_source_round": 1,
    "last_new_raw_source_round": null,
    "previous_gap_judgments_not_verified": [],
    "recovery_decisions_used": 0,
    "stage": "normal"
  }
}
```

## Complete model response

```json
{
  "choices": [
    {
      "finish_reason": "tool_calls",
      "index": 0,
      "message": {
        "content": "The search results point to Vakko (Şen Şapka → Vakko). The Wikipedia snippet mentions Vakkorama and V2K Designers. Let me read the Vakko Wikipedia page to confirm the details, especially the new brand created in the 1980s with the owner's child targeting a younger audience.",
        "role": "assistant",
        "tool_calls": [
          {
            "function": {
              "arguments": "{\"ref\": \"d5\"}",
              "name": "read"
            },
            "id": "call_7e812f2627be4e5a86b70c55",
            "index": 0,
            "type": "function"
          }
        ]
      }
    }
  ],
  "created": 1789482430,
  "id": "chatcmpl-421a63b3-45d9-94eb-b688-62b6d3f46445",
  "model": "glm-5.2",
  "object": "chat.completion",
  "usage": {
    "prompt_tokens": 7259,
    "completion_tokens": 78,
    "reasoning_tokens": 0,
    "total_tokens": 7337,
    "cached_tokens": 3456,
    "prompt_tokens_details": {
      "cached_tokens": 3456
    },
    "prompt_cost": 0.0,
    "completion_cost": 0.0,
    "cache_cost": 0.0
  }
}
```

## Executed action: read

```json
{
  "arguments": "{\"ref\": \"d5\"}",
  "documents": [],
  "evidence": [
    "e1"
  ],
  "executed": true,
  "result": {
    "action_slot_charged": true,
    "evidence": {
      "document": "d5",
      "document_chars": 13639,
      "end": 3000,
      "kind": "raw_evidence",
      "ref": "e1",
      "sha256": "ed282b99cfb0aae5a430ddfadeb3348fa20e85aac24fb4501bf9cd3b3dadb4b2",
      "snapshot": "7d8960afbde4b93401ea738e66299a6ee3d0dee47906ba8e3a86ebdea642ffcd",
      "start": 0,
      "text": "---\ntitle: Vakko - Wikipedia\nauthor: Authority control databases ISNI VIAF\ndate: 2012-04-10\n---\nname: Vakko\nlogo: File:Vakko_Turkish_fashion_company.png\nlogo_size: 100px\nimage_caption: Vakko department store in December 2022\nfoundation: 1934\nfounder: Vitali Hakko\nlocation_city: Istanbul\nlocation_country: Turkey\nkey_people: Cem Hakko (President) Jaklin Guner (CEO)\nindustry: Fashion\nproducts: Luxury goods\nrevenue: $424 million (2023)\nhomepage: vakko.com\n\nVakko is a Turkish luxury fashion company founded by Vitali Hakko (d. 2007) survived by his son Cem Hakko. It produces and retails textiles, leather goods, and accessories.Karen M. Morin, Jeanne Kay Guelke – 2007 – Aperçu – Autres éditionsTurkey – Page 192 Rosie Ayliffe, Marc S. Dubin, Terry Richardson – 2003Istanbul City Guide\n\nVakko also operates luxury department stores under the Vakko name at Zorlu Center, İstinye Park, Akmerkez, Vadi Istanbul, and Akasya malls and on Bağdat Caddesi in Suadiye (Asian side); in Ankara at Atakule and Armada malls, and in İzmir at Hilltown and Istinye Park İzmir malls. It also operates boutiques under the Vakkorama, Vakko Couture, Vakko Wedding, Vakko L'Atelier, and Vakko Home names, as well as Vakko Outlet locations.\"Stores\", Vakko official website\n\nIn 1962, Vakko's eight-story flagship store on İstiklal Avenue in Beyoğlu was the first modern department store in Turkey.\"Heritage\", Vakko website It operated until 2006, when it became a branch of Mango.\"Vakko Beyoğlu'ndan gidiyor yerine en büyük Mango geliyor\" (\"Vakko leaves Beyoğlu and is replaced by the biggest Mango\"), Hürriyet, 29 June 2006\n\nHistory\n\nVakko was founded in 1934 by Vitali Hakko under the brand name Şen Şapka () as a small hat seller in Sultanhamam. In 1937, with his older brother Albert Hakko becoming a partner, Vitali Hakko changed the name of the company to Vakko and established Turkey's first silk dyeing workshop in Kurtuluş, Şişli. After Şen Şapka transformed into Vakko, it started to produce scarves with Turkish silk, cotton and wool. Over time, Vakko turned to ready-to-wear to produce more than hats, scarves, and printed fabrics. Here, customers were introduced for the first time to modern store practices such as bargain-free and promotional sales, and replacement of sold goods.\n\nIn 1962, Hakko opened a large 8-storey store, including a cafe and fashion gallery, in Beyoğlu (a.k.a. Pera), at the time, the most important modern shopping districts in Istanbul. In 1969, the first Vakko Factory was built in Merter measuring 40,000 m2 and employment was provided. In 1973, the second Vakko store opened in Ankara, and Vakko began to further expand its retail network with the Vakko Boutique sales points it opened one after the other. Six years later, in 1979, the third Vakko store opened in İzmir. There was an increase in the popularity of the Vakko brand with advertising campaigns and fashion shows carried out throughout Turkey.\n\nIn September 1979 Vakko opened up its first shop outside Turkey, in Ol"
    },
    "executed": true,
    "next_start": 3000,
    "ok": true,
    "previously_received": false
  },
  "round": 2,
  "tool": "read",
  "tool_call_id": "call_7e812f2627be4e5a86b70c55"
}
```

## Full event records for this request interval

```json
[
  {
    "seq": 28,
    "kind": "model_request",
    "payload": {
      "capacity": 30074,
      "compacted": false,
      "counter": {
        "calibrated_provider_tokens": false,
        "kind": "utf8_bytes"
      },
      "evidence_shelf": [],
      "final": false,
      "output_reservation": 4096,
      "request": "d396615dad514f7252d08fdd7919040e59747178315cdc9cfb8adf740c76d516",
      "round": 2,
      "shelf_evicted_for_capacity": [],
      "visible_documents": [
        "d1",
        "d2",
        "d3",
        "d4",
        "d5",
        "d6",
        "d7",
        "d8",
        "d9"
      ],
      "visible_evidence": [],
      "workflow_view": {
        "active_gap_not_verified": null,
        "available_pages_not_ranked_for_relevance": [
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d9"
            },
            "ref": "d9",
            "snippet": " ... Diversification\n\nIn the 1980s, Stetson began to diversify, releasing the first Stetson cologne in 1981 and Lady Stetson in 1986. Luggage, handbags, umbrell",
            "title": "https://en.wikipedia.org/wiki/Stetson"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d8"
            },
            "ref": "d8",
            "snippet": " ... So, with the advent of highways, there were even more cars and car travel occurring, and fewer people were traveling by train, subway, bus, or tram. So, th",
            "title": "https://www.gentlemansgazette.com/men-stop-wearing-hats/"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d7"
            },
            "ref": "d7",
            "snippet": " ... In interviews with the Irish press, he said he came to London because a poetry editor there had promised that, if he did, the editor would buy him a new tw",
            "title": "https://putthison.com/style-of-allen-ginsberg/"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d6"
            },
            "ref": "d6",
            "snippet": " ... File:Chakchai 2suit.jpg|Example of the two button slim-fit suit popular in the late 2000s in the UK, US and China.\nFile:CSD 2006 Cologne sexy 6.jpg|Woman w",
            "title": "https://en.wikipedia.org/wiki/2000s_in_fashion"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d5"
            },
            "ref": "d5",
            "snippet": " ... In order to bring New York fashion to Istanbul, Vakkorama introduced a new team called V2K Designers ('V2K Designers') in 2000 with the slogan \"Two cities,",
            "title": "https://en.wikipedia.org/wiki/Vakko"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d4"
            },
            "ref": "d4",
            "snippet": " ... Following a decline in sales due to the company's dusty image in the 1970s, Dumas rejuvenates the collections, brings new designers into the company, devel",
            "title": "https://wunderlabel.com/lab/fashion-company-histories/hermes/"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d3"
            },
            "ref": "d3",
            "snippet": " ... Under his reign, the medieval city was transformed into the Paris we know today, with grand boulevards, museums, and iconic structures like the Eiffel Towe",
            "title": "https://www.screwdowncrown.com/p/hermes-luxury-brand-history-birkin-kelly"
          },
          {
            "navigation_seen": true,
            "raw_ranges_delivered": [],
            "read_action": {
              "ref": "d2"
            },
            "ref": "d2",
            "snippet": " ... Hermès\n\nGetty Images\n\nWe started with a saddle shop and we'll end with a saddle shop. In 1837, Thierry Hermès opened a harness workshop for fine equestrian",
            "title": "https://www.mentalfloss.com/article/21572/real-people-behind-10-fashion-houses"
          }
        ],
        "consecutive_repeat_rounds": 0,
        "contract": {
          "enabled": true,
          "gap_state": true,
          "guided_read": true,
          "recovery_rounds": 2,
          "repeat_threshold": 2,
          "repetition": "bounded",
          "reuse_results": true,
          "version": "gap-workflow-v1"
        },
        "instruction": "Use the current missing relation to choose a real next action. Page-name search is not page reading; cached is not proof of progress.",
        "last_new_navigation_source_round": 1,
        "last_new_raw_source_round": null,
        "previous_gap_judgments_not_verified": [],
        "recovery_decisions_used": 0,
        "stage": "normal"
      }
    },
    "previous": "b7846726a96e3f390b5440d7e1245827e77468b96db9fc8f405571bcec93099a",
    "hash": "c7d3226bf39cf446bd356c3b39a02fe22b7e8e957f4c084e60b17039842dca41"
  },
  {
    "seq": 29,
    "kind": "model_response",
    "payload": {
      "elapsed_seconds": 3.0379615999991074,
      "output_charged": 78,
      "raw": "505a0644c150be0614100894633db11cd075ec7db21be26d00597f29a4ca6c6a",
      "response_model": "glm-5.2",
      "round": 2,
      "usage": {
        "cache_read_tokens": 3456,
        "input_tokens": 7259,
        "output_tokens": 78
      }
    },
    "previous": "c7d3226bf39cf446bd356c3b39a02fe22b7e8e957f4c084e60b17039842dca41",
    "hash": "dd00df6a440e65d28fbb6b8048757815c99f88dd09580bf74bc25dfc98661f39"
  },
  {
    "seq": 30,
    "kind": "delivery_ack",
    "payload": {
      "documents": [
        "d1",
        "d2",
        "d3",
        "d4",
        "d5",
        "d6",
        "d7",
        "d8",
        "d9"
      ],
      "evidence": [],
      "round": 2
    },
    "previous": "dd00df6a440e65d28fbb6b8048757815c99f88dd09580bf74bc25dfc98661f39",
    "hash": "19de32b1d2c44270726c5280ac0b778063c98331a95e5cd5c9175c5d85d2650b"
  },
  {
    "seq": 31,
    "kind": "navigation_ack",
    "payload": {
      "object": "9c75b656209d487118d736de5100313f53bc815bbc85b15a212e0f03c354cf73",
      "round": 2,
      "source_round": 1
    },
    "previous": "19de32b1d2c44270726c5280ac0b778063c98331a95e5cd5c9175c5d85d2650b",
    "hash": "c130f926c55d788102c6d4c69c8d8650702df466572581fe6e08ba4eb30e50df"
  },
  {
    "seq": 32,
    "kind": "backend_request",
    "payload": {
      "arguments": {
        "docid": "7624"
      },
      "kind": "get_document",
      "number": 4
    },
    "previous": "c130f926c55d788102c6d4c69c8d8650702df466572581fe6e08ba4eb30e50df",
    "hash": "36f6d0fe8938c42602e7442120c817c814515b0afacfd364482d712b999cecc6"
  },
  {
    "seq": 33,
    "kind": "backend_response",
    "payload": {
      "elapsed_seconds": 0.0018302999960724264,
      "kind": "get_document",
      "object": "0fabb39d62c7ba093e461a0c432220c2e286b354c59c18a0ebb52204e043170b",
      "raw_wire": "0fabb39d62c7ba093e461a0c432220c2e286b354c59c18a0ebb52204e043170b",
      "wire_request": {
        "docid": "7624",
        "kind": "local_sql"
      }
    },
    "previous": "36f6d0fe8938c42602e7442120c817c814515b0afacfd364482d712b999cecc6",
    "hash": "794a3c775d8727df5b4a1556d353f68738efece25a2e1c22e554b7cce319f08b"
  },
  {
    "seq": 34,
    "kind": "snapshot",
    "payload": {
      "characters": 13639,
      "document": "d5",
      "object": "7d8960afbde4b93401ea738e66299a6ee3d0dee47906ba8e3a86ebdea642ffcd"
    },
    "previous": "794a3c775d8727df5b4a1556d353f68738efece25a2e1c22e554b7cce319f08b",
    "hash": "69f1bec47e800615976884d35fc7b23547bc5e22b45fa1ca37bc0fe66c72c623"
  },
  {
    "seq": 35,
    "kind": "evidence_registered",
    "payload": {
      "document": "d5",
      "end": 3000,
      "ref": "e1",
      "sha256": "ed282b99cfb0aae5a430ddfadeb3348fa20e85aac24fb4501bf9cd3b3dadb4b2",
      "snapshot": "7d8960afbde4b93401ea738e66299a6ee3d0dee47906ba8e3a86ebdea642ffcd",
      "start": 0
    },
    "previous": "69f1bec47e800615976884d35fc7b23547bc5e22b45fa1ca37bc0fe66c72c623",
    "hash": "c56363e2690bb63c1e70aabdea36abcb70deb5b07380d320b01c3879efb6ea33"
  },
  {
    "seq": 36,
    "kind": "action_execution",
    "payload": {
      "object": "fbd12e29f6536ce47af3ddcd690a45fc4923d3a9f3f38255f4d702130a910358",
      "round": 2,
      "tool_call_id": "call_7e812f2627be4e5a86b70c55"
    },
    "previous": "c56363e2690bb63c1e70aabdea36abcb70deb5b07380d320b01c3879efb6ea33",
    "hash": "bbd775196f36fc8a1b8f66196e663a56940d124bb17fc5ffebd043da4cc3e2d2"
  },
  {
    "seq": 37,
    "kind": "delivery_preflight",
    "payload": {
      "documents": [],
      "evidence": [
        "e1"
      ],
      "fits": true,
      "phase": "RESEARCH",
      "round": 2
    },
    "previous": "bbd775196f36fc8a1b8f66196e663a56940d124bb17fc5ffebd043da4cc3e2d2",
    "hash": "9c8e51a600f46cbe4d700b05730f50234c9f4723c3dfc63ce214a6ac54570dca"
  },
  {
    "seq": 38,
    "kind": "action_result",
    "payload": {
      "arguments": "{\"ref\": \"d5\"}",
      "executed": true,
      "result": {
        "action_slot_charged": true,
        "evidence": {
          "document": "d5",
          "document_chars": 13639,
          "end": 3000,
          "kind": "raw_evidence",
          "ref": "e1",
          "sha256": "ed282b99cfb0aae5a430ddfadeb3348fa20e85aac24fb4501bf9cd3b3dadb4b2",
          "snapshot": "7d8960afbde4b93401ea738e66299a6ee3d0dee47906ba8e3a86ebdea642ffcd",
          "start": 0,
          "text": "---\ntitle: Vakko - Wikipedia\nauthor: Authority control databases ISNI VIAF\ndate: 2012-04-10\n---\nname: Vakko\nlogo: File:Vakko_Turkish_fashion_company.png\nlogo_size: 100px\nimage_caption: Vakko department store in December 2022\nfoundation: 1934\nfounder: Vitali Hakko\nlocation_city: Istanbul\nlocation_country: Turkey\nkey_people: Cem Hakko (President) Jaklin Guner (CEO)\nindustry: Fashion\nproducts: Luxury goods\nrevenue: $424 million (2023)\nhomepage: vakko.com\n\nVakko is a Turkish luxury fashion company founded by Vitali Hakko (d. 2007) survived by his son Cem Hakko. It produces and retails textiles, leather goods, and accessories.Karen M. Morin, Jeanne Kay Guelke – 2007 – Aperçu – Autres éditionsTurkey – Page 192 Rosie Ayliffe, Marc S. Dubin, Terry Richardson – 2003Istanbul City Guide\n\nVakko also operates luxury department stores under the Vakko name at Zorlu Center, İstinye Park, Akmerkez, Vadi Istanbul, and Akasya malls and on Bağdat Caddesi in Suadiye (Asian side); in Ankara at Atakule and Armada malls, and in İzmir at Hilltown and Istinye Park İzmir malls. It also operates boutiques under the Vakkorama, Vakko Couture, Vakko Wedding, Vakko L'Atelier, and Vakko Home names, as well as Vakko Outlet locations.\"Stores\", Vakko official website\n\nIn 1962, Vakko's eight-story flagship store on İstiklal Avenue in Beyoğlu was the first modern department store in Turkey.\"Heritage\", Vakko website It operated until 2006, when it became a branch of Mango.\"Vakko Beyoğlu'ndan gidiyor yerine en büyük Mango geliyor\" (\"Vakko leaves Beyoğlu and is replaced by the biggest Mango\"), Hürriyet, 29 June 2006\n\nHistory\n\nVakko was founded in 1934 by Vitali Hakko under the brand name Şen Şapka () as a small hat seller in Sultanhamam. In 1937, with his older brother Albert Hakko becoming a partner, Vitali Hakko changed the name of the company to Vakko and established Turkey's first silk dyeing workshop in Kurtuluş, Şişli. After Şen Şapka transformed into Vakko, it started to produce scarves with Turkish silk, cotton and wool. Over time, Vakko turned to ready-to-wear to produce more than hats, scarves, and printed fabrics. Here, customers were introduced for the first time to modern store practices such as bargain-free and promotional sales, and replacement of sold goods.\n\nIn 1962, Hakko opened a large 8-storey store, including a cafe and fashion gallery, in Beyoğlu (a.k.a. Pera), at the time, the most important modern shopping districts in Istanbul. In 1969, the first Vakko Factory was built in Merter measuring 40,000 m2 and employment was provided. In 1973, the second Vakko store opened in Ankara, and Vakko began to further expand its retail network with the Vakko Boutique sales points it opened one after the other. Six years later, in 1979, the third Vakko store opened in İzmir. There was an increase in the popularity of the Vakko brand with advertising campaigns and fashion shows carried out throughout Turkey.\n\nIn September 1979 Vakko opened up its first shop outside Turkey, in Ol"
        },
        "executed": true,
        "next_start": 3000,
        "ok": true,
        "previously_received": false
      },
      "round": 2,
      "tool": "read",
      "tool_call_id": "call_7e812f2627be4e5a86b70c55"
    },
    "previous": "9c8e51a600f46cbe4d700b05730f50234c9f4723c3dfc63ce214a6ac54570dca",
    "hash": "a993b886f9ba11e7ca8f904deb180c845628ed493ea261acb86c971101978dc5"
  },
  {
    "seq": 39,
    "kind": "round_end",
    "payload": {
      "group": "202f394726b97757a7e0dd395ad472164b489a4fc91744c15f018875b1a7bb5e",
      "notes": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      "remaining": {
        "action_slots": 198,
        "backend_calls": 116,
        "model_calls": 2,
        "output_reservation": 47783
      },
      "round": 2
    },
    "previous": "a993b886f9ba11e7ca8f904deb180c845628ed493ea261acb86c971101978dc5",
    "hash": "c9a03e259e6f347d0cb0d2ff148e3272199014fabc92335b67a58dbed6210cf9"
  }
]
```
