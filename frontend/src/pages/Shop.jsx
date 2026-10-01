/*
  Shop page
  =========
  Product grid with category filter and search.
*/

import { useEffect, useState } from 'react'
import { api } from '../api'
import ProductCard from '../components/ProductCard'

export default function Shop() {
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [category, setCategory] = useState('All')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    api
      .listCategories()
      .then((data) => {
        if (!cancelled) setCategories(data)
      })
      .catch(() => {
        /* The filter bar is a nicety; failing to load it is not fatal. */
      })

    return () => {
      cancelled = true
    }
  }, [])

  // Debounce so typing does not fire a request per keystroke.
  useEffect(() => {
    let cancelled = false
    setLoading(true)

    const timer = setTimeout(() => {
      api
        .listProducts({ category, search })
        .then((data) => {
          if (!cancelled) {
            setProducts(data)
            setError('')
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err.message)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, 250)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [category, search])

  return (
    <div className="page">
      <section className="hero">
        <h1 className="hero-title">Kits and gear for match day</h1>
        <p className="hero-sub">
          Free shipping over $100. Ordered before 2pm and it ships the same day.
        </p>
      </section>

      <div className="toolbar">
        <div className="filter-pills" role="group" aria-label="Filter by category">
          {['All', ...categories].map((name) => (
            <button
              key={name}
              className={`pill ${category === name ? 'active' : ''}`}
              onClick={() => setCategory(name)}
            >
              {name}
            </button>
          ))}
        </div>

        <input
          type="search"
          className="search"
          placeholder="Search products…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search products"
        />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="product-card skeleton" />
          ))}
        </div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <h2>Nothing matched that</h2>
          <p>Try a different search or category.</p>
        </div>
      ) : (
        <div className="grid">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}
