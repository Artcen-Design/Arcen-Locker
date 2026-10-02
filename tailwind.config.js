/** Used to build vendor/tailwind.css locally instead of the CDN JIT compiler.
 * Rebuild after adding new Tailwind classes anywhere in index.html or js/:
 *   tailwindcss -i vendor/tailwind.input.css -o vendor/tailwind.css --minify
 * (grab the standalone CLI matching this config's v3 syntax from
 * https://github.com/tailwindlabs/tailwindcss/releases if you don't have it)
 */
module.exports = {
    darkMode: 'class',
    content: ['./index.html', './js/**/*.js'],
};
