---
title: Hackathons & SDG
layout: default
description: Driving education and research through SDG-aligned hackathons.
---

<section>
  <h1>Hackathons for Education/Research (SDG)</h1>
  <p class="item-summary">
    How I help turn SDG-aligned themes into collaborative learning and research outputs via hackathons.
  </p>

  <div class="hero-grid" role="list">
    {% assign items = site.sdg_hackathons | where_exp: "i", "i.published != false" | sort: "year" | reverse %}
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
        {% if item.sdg_tags %}
          <p class="card-desc">
            {% for tag in item.sdg_tags %}
              <span style="display:inline-block;margin-right:0.5rem;color:#0f766e;">{{ tag }}</span>
            {% endfor %}
          </p>
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

