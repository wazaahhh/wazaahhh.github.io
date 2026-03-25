---
title: Grants & Awards
layout: default
description: Grants, proposal reviews, and recognition.
---

<section>
  <h1>Grants & Awards</h1>
  <p class="item-summary">
    Funding, proposal reviews, and institutional partnerships connected to research and education.
  </p>

  <div class="hero-grid" role="list">
    {% assign items = site.grants | where_exp: "i", "i.published != false" | sort: "year" | reverse %}
    {% for item in items %}
      <div class="card" role="listitem">
        <a href="{{ item.url | relative_url }}">
          <div class="card-title">{{ item.title }}</div>
        </a>
        {% if item.summary %}
          <p class="card-desc">{{ item.summary }}</p>
        {% endif %}
        {% if item.year %}
          <p class="card-desc"><strong>{{ item.year }}</strong></p>
        {% endif %}
        {% if item.links and item.links.size > 0 %}
          <div class="card-desc">
            {% for link in item.links %}
              <a href="{{ link.url }}" style="display:inline-block;margin-right:0.75rem;">{{ link.label }}</a>
            {% endfor %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  </div>
</section>

