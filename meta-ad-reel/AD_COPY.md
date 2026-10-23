# ark_artworks_ — Meta ad: reel + copy

## Files

| File | Use it for |
|---|---|
| `output/ark_artworks_ad_reels-9x16.mp4` | Reels and Stories placements (1080×1920, 30 s, with music) |
| `output/ark_artworks_ad_reels-9x16_no-music.mp4` | Same video, silent, so you can add a track from Meta's sound library |
| `output/ark_artworks_ad_feed-4x5.mp4` | Facebook and Instagram Feed (1080×1350) |
| `output/cover_*.jpg` | Thumbnail / cover frame |

All on-screen text sits inside Meta's Reels safe zone, so it stays clear of the top 14% (profile bar) and the bottom 35% (caption and CTA button).

## Storyboard (30 s)

| Time | Scene | On-screen text |
|---|---|---|
| 0–2.5 s | An empty warm-plaster wall. *Convergence* fades onto it. | ORIGINAL ABSTRACT ART · *Your walls have been quiet long enough.* |
| 2.5–6.9 s | *Convergence* above a light oak fluted sideboard with an ivory vase and travertine bowl. The camera then pushes into the texture. | NO. 01 — CONVERGENCE · *Bold, but never loud.* |
| 6.3–13.2 s | The camera pulls back from the brushwork to *Morning Light* in a warm greige room with palm shadows, a walnut bench and a cream linen throw. | NO. 02 — MORNING LIGHT · *Soft light. Slow mornings.* |
| 12.6–19.5 s | *Solstice* on a warm sand wall with window light and a travertine-and-oak console. | NO. 03 — SOLSTICE · *A little sunshine that never sets.* |
| 18.9–25.8 s | *Grove* on a soft white wall with olive-leaf shadows, a white fluted sideboard and white and charcoal ceramics. | NO. 04 — GROVE · *Warm earth, fresh green.* |
| 25.2–30 s | All four paintings together on a gallery wall under picture lights, with a leather bench. | @ark_artworks_ · *Four originals. One belongs on your wall.* · HAND-PAINTED · CUSTOM SIZES |

The rooms are 3D-rendered in Blender (Cycles) with simulated daylight through a window, so the light, shadows and materials behave like a photograph. Each painting is pasted pixel-for-pixel onto its panel and takes on only that panel's light and shadow.

Each room is a neutral backdrop (warm white, greige, sand or soft white) with natural materials: oak, walnut, linen, travertine and ceramic. No prop repeats a colour from its painting, so the painting is the only colour in the room. The paintings are used exactly as photographed and are only resized.

> **Painting names:** *Convergence* is the title from your post. *Morning Light*, *Solstice* and *Grove* are working titles I picked. To change them, edit `PAINTINGS` in `build_reel.py` and re-run.

---

## Primary text (the caption above the ad). Pick one, or A/B test them

**A — Short and calm**
> Some walls just need the right painting.
> Four hand-painted abstracts, each made to set the mood of a room. Which one feels like yours? 🤍

**B — Story**
> Every painting here started as a blank canvas and a feeling.
> Bold red for the room that starts conversations. Soft blue for slow mornings. A little sunshine that never sets. Warm greens for the space you come home to.
> Original, hand-painted, and made in the size your wall needs.

**C — Conversation starter** (good for engagement campaigns)
> Quick question: which room would you walk into first?
> 01 Convergence · 02 Morning Light · 03 Solstice · 04 Grove
> Tell us your number 👇

**D — For designers and businesses**
> Designing a lobby, café or a client's living room?
> Original abstract paintings in custom sizes, made to fit the space rather than the other way round.

## Headline (under the video, 40 characters or fewer)
- Original art for walls with personality
- Hand-painted. Made for your space.
- Find the painting your wall is missing
- Four originals. One is yours.

## Description (optional, under the headline)
- Hand-painted abstract art · Custom sizes
- Original textured paintings for homes and interiors

## Call-to-action button
- **Learn More** for a website or shop
- **Send Message** for DM / WhatsApp sales, which suits commissions and custom sizes best
- **Shop Now** only if you have a checkout page

## Instagram caption (if you also post it organically)
> Your walls have been quiet long enough. ✨
>
> Four original paintings, four different moods:
> 01 Convergence: bold, but never loud
> 02 Morning Light: soft light, slow mornings
> 03 Solstice: a little sunshine that never sets
> 04 Grove: warm earth, fresh green
>
> Which room would you walk into first? 1–4 👇
> Hand-painted abstract art · Custom sizes
>
> #abstractart #originalart #interiordesign #homedecor #wallart #interiordecor #artforsale #modernart #texturedart #homeinteriors #artcollector #livingroomdecor

## Targeting starting point
- **Interests:** interior design, home decor, art collecting, architecture, Architectural Digest, Elle Decor, Houzz, Pinterest, IKEA, boutique hotels.
- **Behaviours:** recently moved, engaged shoppers.
- **Ages:** 27–60. Start broad (Advantage+ audience) and let the video's engagement guide delivery.
- **Retarget:** people who watched 50% or more of this video, using caption D or a close-up of a single painting.

## Re-building / editing the video
```bash
pip install numpy pillow scipy
pip install bpy               # Blender as a Python module, for the 3D rooms
python3 render3d.py              # renders all rooms into .cache/ (add --draft for quick previews)
python3 build_reel.py            # 9:16 Reels/Stories
python3 build_reel.py --feed     # 4:5 Feed
python3 build_reel.py --preview 2.4 10 29   # quick stills at those seconds
```
The 3D rooms are defined in `render3d.py` (`build()`); `scenes.py` holds the older flat-illustration rooms, which are only used if `.cache/` has no 3D renders. Re-run `render3d.py <room>` after editing a room.
