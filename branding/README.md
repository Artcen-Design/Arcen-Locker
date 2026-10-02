Drop this site's client logo(s) here, then set in `.env`:

```
BRAND_LOGO=branding/logo_a.png
BRAND_LOGO_DARK=branding/logo_b.png
BRAND_COLOR=#111827
BRAND_FOOTER=soporte@cliente.com
```

`BRAND_LOGO_DARK` is optional — leave it blank and dark mode just reuses
`BRAND_LOGO`. The logo image should already include the client's name if you
want one shown; there's no separate text label anymore.

Leave everything blank to fall back to the default look (no logo header,
default blue button, no footer). `BRAND_NAME` (also optional) is only used
as the logo's alt text for accessibility, not shown on screen.
