# Decision templates

A decision template sets how decisions are presented in your organisation:

- the three section headings of a decision and the prompts under them,
- the example titles shown in the form,
- the list of decision types people can pick from,
- the relationship packs suggested with it.

A template does not change what is stored. Every decision still has a title, three text sections and a status. In the API and in exports the sections keep the names `context`, `decision` and `consequences`, whatever headings the template shows.

> Changing the template changes headings and prompts only. Your decisions are not altered, and you can change back at any time.

## Choosing a template

Administrators and stewards choose the template under **Organisation Settings > Decision template**. The card shows a preview of the headings before anything is saved.

- A new organisation is asked one optional question in the first administrator's welcome dialog ("What kind of organisation are you?"). Skipping it means the General template. The Community Edition setup wizard asks the same optional question.
- An organisation that existed before templates sees one notice on the decision list, shown to administrators and stewards. "Choose a template" and "Not now" both end it for the whole organisation.
- An organisation that chooses nothing stays on General, which is the wording the product had before templates.

## The five templates

| Template | Headings | Typical use |
|---|---|---|
| **General** (default) | Context / Decision / Consequences | Any kind of decision: pricing, suppliers, hiring, ways of working |
| **Software and technology** | Context / Decision / Consequences | Software, IT and platform teams. Same headings as General; the prompts, types and suggested packs follow the usual architecture decision record |
| **Controlled change** | Change and reason / Decision and approval / Impact and follow-up | Changes to a product, process, plant, drawing or contract that are assessed and approved before they are made |
| **Governance and committee** | Matter and background / Decision and reasons / Alternatives, interests and implications | Boards, trustees, committees and officers deciding under a stated authority |
| **Investment and approval** | Proposal and assessment / Decision and conditions / Risks and monitoring | Investment, credit and large spending decisions taken under a mandate |

The three headings of every template mean the same as context, decision and consequences. That is why text written under one template still reads correctly under another.

Two templates carry a caution, shown with the form:

- Controlled change: "This layout follows common change-record practice. It does not replace your quality or safety management system."
- Governance and committee: "Do not record decisions about identifiable patients, pupils or service users here."

The templates are layouts based on how such records are commonly written. Using one does not make an organisation meet any legal or regulatory requirement.

## Industry

The industry answer is optional. It only suggests a template; an administrator can pick any of the five. A bank's IT department may want Software and technology, and a manufacturer's board may want Governance and committee.

The list is the 22 sections of NACE Rev. 2.1, with their official English titles. Only the section letter is stored. It is kept with the organisation's settings and is not sent to analytics.

| | Section | Suggested template |
|---|---|---|
| A | Agriculture, forestry and fishing | General |
| B | Mining and quarrying | Controlled change |
| C | Manufacturing | Controlled change |
| D | Electricity, gas, steam and air conditioning supply | Controlled change |
| E | Water supply; sewerage, waste management and remediation activities | Controlled change |
| F | Construction | Controlled change |
| G | Wholesale and retail trade | General |
| H | Transportation and storage | General |
| I | Accommodation and food service activities | General |
| J | Publishing, broadcasting, and content production and distribution activities | General |
| K | Telecommunication, computer programming, consulting, computing infrastructure and other information service activities | Software and technology |
| L | Financial and insurance activities | Investment and approval |
| M | Real estate activities | General |
| N | Professional, scientific and technical activities | General |
| O | Administrative and support service activities | General |
| P | Public administration and defence; compulsory social security | Governance and committee |
| Q | Education | Governance and committee |
| R | Human health and social work activities | Governance and committee |
| S | Arts, sports and recreation | General |
| T | Other service activities | General |
| U | Activities of households as employers and undifferentiated goods- and service-producing activities of households for own use | General |
| V | Activities of extraterritorial organisations and bodies | Governance and committee |

Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0. The section titles are reproduced unchanged; the "Suggested template" column is ours.

## Decision types

Each template has a short list of decision types, for example "Policy" and "Spending" in General or "Appointment" and "Service change" in Governance and committee.

- A type is optional. A decision without a type is complete.
- Anyone who can edit a decision can set its type, in the decision form. The type is shown on the decision and on its card, and the decision list can be filtered by type.
- If the organisation changes template later, a decision keeps the type it has. The type is shown as it is, and stays selectable for that decision, even when the new template does not list it. Nothing is erased or renamed.

### Giving existing decisions a type

Under **Organisation Settings > Decision template**, the card "Decision types for existing decisions" lists the organisation's decisions with tick-boxes. Filter by search text, status or current type, tick the decisions, then use **Set type** or **Clear type**.

Only the type changes. Titles, text, status and the last-updated date of the decisions stay as they are. The change is recorded in the organisation's audit log.

## Relationship packs

Each template suggests relationship packs (see Organisation Settings > Decision Relationships). They are switched on only if the administrator ticks "Also switch on the suggested relationship packs" when saving. Packs are only ever added; a pack that is already on is never switched off.

## Where the template is not used yet

Notification emails, Slack and Teams messages, the external AI REST API and exports still say Context, Decision and Consequences. See `docs/TODO.md`.

The MCP server (Enterprise Edition) does use it. Its tool `get_decision_template` returns the organisation's headings, guidance and decision types; decisions it returns carry `decision_type` and `section_headings`; `create_decision` accepts a `decision_type` under the same rule as the web app; `list_decisions` and `search_decisions` can filter by it. The field names stay `context`, `decision` and `consequences`.

## API

| Endpoint | Who | Purpose |
|---|---|---|
| `GET /api/decision-templates/catalog` | Anyone | The five templates and the industry list |
| `GET /api/tenant/decision-template` | Any member | The organisation's template and industry |
| `PUT /api/tenant/decision-template` | Administrators and stewards | Body: `template_id`, `industry`, `enable_suggested_packs`. A field left out keeps its value; `null` clears it |
| `POST /api/tenant/decision-template/dismiss-notice` | Administrators and stewards | Ends the notice for the organisation |
| `POST /api/tenant/decisions/bulk-type` | Administrators and stewards | Body: `decision_ids` (at most 200), `decision_type` (`null` clears) |

`POST /api/decisions` and `PUT /api/decisions/<id>` accept an optional `decision_type`. It must be one of the types of the organisation's current template, or the type the decision already has. Decisions and their history entries are returned with `decision_type`.

The catalogue is defined in `decision_templates.py`.
