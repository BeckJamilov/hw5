# AI Prompts — HW5: Campus Customs Multi-Agent Operations

This file records the prompts used with the AI coding assistant during this assignment, organized by problem.

---

## Problem 1: Vibe coder prompts

### Prompt 1

> We are starting my HW5 project called Campus Customs Multi-Agent Operations. For now I want to work only on Problem 1. Create a file called AI_prompts.md in the root of the project. This file will keep all prompts I send you during this assignment. Make a section called '''Problem 1: Vibe coder prompts''' and record this first prompt there. For each next problem we will add a new section with its problem number and title, the prompts I actually used, and follow-up prompts with a short explanation of what was missing after the first prompt, if needed. Do not invent any prompts or work on the next problems yet.

---

## Problem 2: Study the Campus Customs database

### Prompt 1

> Now let's work on Problem 2: Study the Campus Customs database. First check if we have data/campus_customs.db in our project. If it is not there, tell me so I can download and add data.zip. If it is there, open the database and check all tables and their fields. Also look at the three open tickets 101, 102 and 103 and understand how they are connected to other tables. Make a copy of the original database called data/campus_customs_new.db and don't change the original file. Then create output/harness.md and write all table names, their fields and one short explanation why each table is important for our agents. Also explain what each of the three tickets is about based on the actual database information. Add this prompt to AI_prompts.md under Problem 2. Don't start Problem 3 yet.

---

## Problem 3: Build the MCP server

### Prompt 1

> Now let's do Problem 3: Build the MCP server. Create mcp_server/ using FastMCP and connect it to our working database data/campus_customs_new.db. I want three tools for our three tickets. First tool should help with ticket 101 by checking the customer order, available inventory, unpaid vendor invoice and vendor lead time. Second tool should help with ticket 102 by checking the rent amount, due date, current cash balance and any related payments. Third tool should help with ticket 103 by checking the bulk hoodie order, available stock, selling price, cost and restocking options. Make sure all information comes from our actual database and use the correct table fields we found in Problem 2. Don't make up any data. For now these tools should only read information and not change anything in the database. Use clear names for the tools. In output/harness.md list each tool, the tables it reads, which ticket it helps with and why we need it. Also create mcp_server/README.md explaining what this server does, which database it uses and the three tools. Add this prompt to AI_prompts.md under Problem 3. Don't connect or test the server yet and don't start Problem 4.

### Follow-up prompt 1

**What was missing:** The ticket 103 tool listed every vendor as a restocking option, including vendors that don't supply apparel, and it didn't check the shop rule that vendors with open unpaid invoices can't ship new products.

> I think we need one small improvement in Problem 3. In the tool for ticket 103, we should not show every vendor as a possible restocking option because some vendors do not supply apparel. Also check if the suitable vendor has any open unpaid invoices, because according to our shop rules they cannot ship new products until these invoices are paid. Please update the tool using only our database information, and update mcp_server/README.md and output/harness.md if needed. Keep the tools read-only. Also record this follow-up prompt in AI_prompts.md with one sentence explaining what was missing before. Don't start Problem 4 yet.

---

## Problem 4: Add the MCP server to vibe coder and test each tool

### Prompt 1

> Now let's work on Problem 4: Add the MCP server to vibe coder and test each tool. Connect our MCP server to this project using .mcp.json so you can actually call the tools. Make sure the server uses data/campus_customs_new.db. Then test all three tools one by one using the MCP connection, not by simulating their outputs. Check that the results match the actual database information. Save the results in output/mcp_smoke.json and for each tool include the prompt I asked you, the tool name and the actual output it returned. Also check that the Problem 3 documentation includes the invoices table for the hoodie tool and update it if missing. Add this prompt to AI_prompts.md under Problem 4. Tell me if any tool or connection fails and don't start Problem 5 yet.

### Follow-up prompt 1

**What was missing:** After Prompt 1 created `.mcp.json`, the campus-customs MCP server wasn't available yet because Claude Code only loads `.mcp.json` servers when a session starts. So the tools couldn't be called through MCP, and we had to restart the session before running the real tests.

> I restarted the session. Now please continue Problem 4 where we stopped. Check if you can access our campus-customs MCP server and call all three tools through MCP, one by one. Save the real outputs in output/mcp_smoke.json with the prompt, tool name and returned output for each test. Check if all values match our working database. Also record this follow-up prompt in AI_prompts.md and explain that we needed to restart the session because MCP was not available before. Don't start Problem 5 yet.

---

## Problem 5: Build the agent team and grow the MCP tools

### Prompt 1

> Now let's work on Problem 5: Build the agent team and grow the MCP tools. I want to create five agents using PydanticAI: Boss, Inventory, Accounting, Facilities and Customer Service. Boss should read tickets, decide who should work on them and make final decisions. Inventory should check stock, shortages and vendors. Accounting should check cash, invoices, margins and prepare payments or purchases for human approval. Facilities should handle rent and leases. Customer Service should prepare customer messages but not send them. Make separate prompt files for all five agents in backend/prompts/ and put the data types in backend/models.py. Make the agent instructions detailed and include the shop rules that each agent needs. All agents should be able to delegate tasks to each other, not only through Boss. Use only gpt-6-luna through Portkey with PORTKEY_API_KEY for every agent. All shop information and actions must go through our MCP server connected to data/campus_customs_new.db, so don't create another database tool system outside MCP. Add more MCP tools if needed for the tickets. Make sure no payment or purchase can happen without human approval, cash cannot become negative, and agents don't send real emails. Also add output/audit_trail.json to record each agent step, delegation, tool call and result, and make sure new runs append instead of deleting old records. Put reasonable limits on agent loops and token usage. Update output/harness.md with all agents, tools, tables and safety rules, and update mcp_server/README.md with the new tools. Record this prompt in AI_prompts.md under Problem 5. Don't start Problem 6 or run the full tickets yet.

### Follow-up prompt 1

**Why we changed the limits:** The first limits (40 model requests, 60 tool calls, 300,000 tokens, 4,000 output tokens per response, 8 delegations) were higher than three small tickets need. One runaway run could have used a lot of Portkey credits, so we lowered them while keeping one budget shared by the whole team per ticket.

> I think Problem 5 looks good, but our token limits are too high and I don't want to waste my Portkey credits. Please reduce the limits in backend/agents.py to maximum 24 model requests, 40 tool calls, 80000 total tokens, 2000 output tokens per response and 6 delegations per ticket. Keep maximum delegation depth at 3. Make sure these limits are shared by all five agents and not separate for each one. Update output/harness.md with these numbers and add this follow-up prompt to AI_prompts.md with a short explanation of why we changed the limits. Don't change anything else and don't start Problem 6 yet.

---

## Problem 6: Plan the three tickets

### Prompt 1

> Now let's do Problem 6: Plan the three tickets. Create output/desk_tickets.html as a standalone HTML page that I can open by double clicking it. Make five working tabs called 101, 102, 103, Cash and Reflection. For tickets 101, 102 and 103, write only the Expected section for now and leave the Actual section empty because we haven't run our agents yet. Use the real ticket information from our database and the agents and MCP tools we already built. For each ticket explain which agent Boss should call first and why, then show all the delegations we expect between the agents in the correct order, and which MCP tools each agent should use. Don't just make Boss call all five agents, only involve agents who are needed for that ticket. Make the expected plans specific to our three tickets and consider the unpaid invoice, rent, cash balance, inventory shortages and human approval rules. Leave Cash and Reflection tabs empty or with a short coming later message. Make the page clean and easy to read. Don't run any agents, make payments or change the database yet. Add this prompt to AI_prompts.md under Problem 6 and don't start Problem 7.

### Follow-up prompt 1

**What we corrected:** The first version of the page said a human should "review and send" the customer drafts, but our assignment says drafts stay on the board and customers aren't emailed. For ticket 101 it also said the reprint was "on the way" without any shipping confirmation. Now it says size S depends on paying invoice 501 and on Bulldog Print Co actually shipping the reprint.

> I reviewed Problem 6 and found two small things to fix in output/desk_tickets.html. First, our assignment says customer drafts must stay on the board, so don't say that a human should send them. They can review the drafts but we should not email customers. Second, for ticket 101 don't say the reprint is already on the way because we don't have confirmation of shipping. Make it clear that it depends on paying invoice 501 and the vendor shipping the product. Keep all other plans, numbers, design and tabs the same. Add this follow-up prompt to AI_prompts.md with a short explanation of what we corrected. Don't start Problem 7 yet.

### Follow-up prompt 2

**What we corrected:** After the page fix, the agent instructions still said a human "reviews and sends" customer drafts. That would have told the agents to plan for emailing customers, which our assignment doesn't allow. The Customer Service and Boss prompts, the `TicketDecision` field descriptions in `backend/models.py`, and `output/harness.md` now say drafts stay on the board for human review and customers are never emailed.

> Yes, please also fix the 'human reviews and sends' wording in backend/prompts/customer_service.md, backend/prompts/boss.md, backend/models.py and output/harness.md so drafts stay on the board and are never emailed. Add it to AI_prompts.md as a follow-up. Don't start Problem 7.

---

## Problem 7: Backend routes

### Prompt 1

> Now let's work on Problem 7: Backend routes. Create backend/main.py using FastAPI and connect it with our existing five agents and MCP server. We need API routes to get all three tickets and their status, run our agent team for one selected ticket, get recent agent events from audit_trail.json so the dashboard can show what agents are doing, approve and execute a payment or purchase only after a human clicks approve, get the current checking balance, and reset the working database to the original values. Also add a route to get pending approval requests so we can show them in the dashboard later. Make sure the backend uses our existing MCP tools and agent system, not another separate database system. Only the human approval route should execute payments, and agents should never be able to approve their own requests. Check available cash before payment and don't allow negative balances or duplicate payments. The reset should only replace campus_customs_new.db and never change the original database. Also allow the future React frontend at http://localhost:5173 to call the backend at http://localhost:8000. Keep ticket status accurate, so don't mark something resolved if it still needs human approval. Test the API routes without running the full AI agents or spending Portkey tokens. Update output/harness.md with the routes and what each one does, and add this prompt to AI_prompts.md under Problem 7. Don't start Problem 8 yet.

### Follow-up prompt 1

**What was missing:** The reject route in `backend/main.py` didn't check for an active agent run, while the approve and reset routes did. A human could reject a request while agents were still working on the same tickets. The same `409` check was added and tested without Portkey tokens: rejecting during a simulated run was blocked, and rejecting after the run worked (7/7 checks).

> One small thing before we finish Problem 7. Please check if the reject approval route in backend/main.py blocks rejection while an agent run is active, same as the approve and reset routes. If it doesn't, add this check and test it without using Portkey tokens. Record this follow-up in AI_prompts.md. Don't change anything else and don't start Problem 8 yet.

---

## Problem 8: Agent dashboard

### Prompt 1

> Now let's do Problem 8: Agent dashboard. Build a React + Vite + TypeScript frontend in frontend/ and connect it to our FastAPI backend at http://localhost:8000. I want a nice looking dashboard where I can see all three tickets, select one ticket and run the agent team, see what each agent is doing and saying, and see when a ticket is resolved or waiting for human approval. Also show a short summary of what agents did, pending payments or purchases with approve and reject buttons, and the current checking balance that updates after payments. Make sure the dashboard uses our existing backend API routes and doesn't make up any results. Use a clean modern dark design with good colors, separate sections for tickets, agent activity, approvals and cash. Make it look professional but don't spend too much time on unnecessary animations or complicated features. Add CORS support if needed. Test that the frontend builds and connects to the backend, but don't run the actual AI agents yet because we will do that in Problem 9. Create output/design.md explaining the layout, how agents are shown differently, how tickets and cash are displayed, and why you chose this design. Add this prompt to AI_prompts.md under Problem 8. Don't start Problem 9 yet.

---

## Problem 9: Resolve the tickets

### Prompt 1

> Now let's work on Problem 9: Resolve the tickets. My React dashboard is not opening in the browser, so first quickly check what is wrong and make sure both backend and frontend are running. Don't spend too much time on design or small issues. Before running the agents, reset data/campus_customs_new.db to the original values and record the starting checking balance. Then run our real five-agent team on tickets 101, 102 and 103 using only gpt-6-luna through Portkey. Do them one by one and use the actual MCP tools and database, not fake results. If any payment or purchase needs human approval, stop and tell me exactly what I need to approve. Never approve payments yourself. Keep customer messages as drafts only. After running the tickets, fill the Actual sections in output/desk_tickets.html based on real audit events, including agents, delegations and tools, and fill the Cash tab with starting balance, changes for each ticket and ending balance matching the database. Save output/resolved_tickets.json with ticket status, outcome, agent contributions and human approvals. Also create output/resolved_board.html with real screenshots of the React dashboard showing each ticket, not invented screenshots. Keep appending to output/audit_trail.json and update output/harness.md and AI_prompts.md. Do not invent successful results if something fails. Tell me clearly what is finished and what still needs my action. Don't start Problem 10 yet.

**What happened:** The dashboard wasn't opening because neither server was running. The first real run then failed because Portkey/Azure doesn't allow function tools on gpt-6-luna chat completions with reasoning on. `openai_reasoning_effort="none"` was set in `backend/agents.py`, and all three tickets then ran successfully. No payments were approved.

### Follow-up prompt 1

**What was missing:** After the agent runs, the human approved and paid both requests on the dashboard. The Problem 9 files still showed the earlier state: $3,400 with two pending approvals. They also didn't explain why the dashboard shows −$2,240 "after all open bills". That figure is a forecast that now includes October's rent, because paying rent moved the lease's due date to 2026-10-02. It is not a negative balance.

> The human approved and paid both requests on the dashboard. Invoice 501 was $840 and rent was $2400. Checking balance is now $160 and there are no pending approvals. Please check the actual status of tickets 101, 102 and 103 and finish Problem 9 using our real database and audit trail. If ticket 103 was not run yet, tell me before doing anything else. Fill the Actual sections and Cash tab in output/desk_tickets.html, create output/resolved_tickets.json and output/resolved_board.html using real dashboard screenshots. Make sure the cash calculations are correct and explain why the dashboard shows -$2240 after all open bills. Don't reset the database, don't repeat payments and don't invent results. Update output/harness.md and AI_prompts.md. Keep this quick and don't start Problem 10 yet.

### Follow-up prompt 2

**What was missing:** Ticket 103 was still waiting for the human pricing decision, and draft #2 still showed customers our unit cost, margin, and the unpaid vendor invoice. The decision (10% off for the 8 in-stock hoodies only, with the other 12 not promised) was recorded through `record_ticket_decision` as Beck Jamilov, which resolved ticket 103 without any payment, purchase, or delivery. Draft #2 was corrected in place with a new human-only MCP tool, `revise_customer_message_draft`, because the existing system could only add drafts, not fix them. It stays on the board and nobody was emailed.

> For ticket 103, I am making the human decision now. I approve 10% discount for the 8 hoodies we currently have in stock, but we cannot promise the remaining 12 until we have enough cash and vendor can ship. Please record my decision through our existing system and finish ticket 103 if the discount request can be considered resolved. Don't mark all 20 hoodies as delivered or paid. Also fix customer draft #2 because it mentions our internal unit cost and vendor invoice, which customers should not see. Keep all drafts on the board and don't email anyone. Update the Actual section, resolved_tickets.json, resolved_board.html if needed, audit trail and AI_prompts.md. Don't reset the database or repeat any payments. Keep it quick and don't start Problem 10 yet.

---

## Problem 10: Reflection

### Prompt 1

> Now let's do Problem 10: Reflection. Please put the following answers into the Reflection tab of output/desk_tickets.html. Keep the same design and don't change the other tabs. These answers are based on our real agent runs and I want to use exactly these points, without making them more academic. Format them nicely in HTML with headings and paragraphs. Also add this prompt to AI_prompts.md under Problem 10. Don't start Problem 11 yet.
>
> 1. How would you evaluate the performance of the agents on each ticket and why?
>
> For ticket 101, I think the agents did pretty well. Inventory checked the stock and found that we have zero Bulldog tees in size S. It also found that invoice 501 for $840 was overdue and Bulldog Print Co could not ship until we pay it. Accounting checked our cash and prepared a payment request, while Customer Service drafted a message for Tauhid Zaman. Boss coordinated everything and waited for my approval instead of making the payment itself. After I approved $840, the ticket was marked resolved. However, the agents used 16 model requests and 19 tool calls, which seems quite a lot for this task. Also, the shirt was not actually delivered, so resolving the ticket doesn't mean the customer already received the product.
>
> For ticket 102, the result was also good. Facilities verified that Elm City Properties was our actual landlord and the rent was $2,400 due on September 2. Accounting prepared the payment request and I approved it. The system recorded the payment and changed the next rent date to October 2. However, Facilities made one mistake. It said we would have $1,000 after paying rent, but it did not properly consider the $840 invoice payment already requested. Accounting and Boss understood that after both payments we would only have $160. This shows why financial numbers should be checked carefully.
>
> For ticket 103, I think the agents made a reasonable recommendation. Inventory found that we had only 8 size M hoodies while Yale AI Club wanted 20. Accounting calculated that buying another 12 would cost $264, but we only had $160 available after the other payments. It also checked the discount and suggested 10%, which gives $52.20 per hoodie compared to the $22 unit cost. I approved this discount for the 8 available hoodies only. The main problem was Customer Service, because its first draft included our internal cost, margin and unpaid vendor invoice. I had to correct it manually. The final draft stayed on the board and was not sent. Ticket 103 was resolved as a pricing decision, but no hoodies were sold or delivered.
>
> 2. For each ticket, how did Actual compare to Expected?
>
> For ticket 101, I expected Boss to delegate to Inventory, then Inventory to Accounting, and Boss to Customer Service. In reality, Boss delegated directly to Inventory, Accounting and Customer Service. So the business result was close to what I expected, but the delegation was different. The invoice payment request and customer draft were created correctly, and I approved the payment later.
>
> For ticket 102, I expected Boss to call Facilities and then Facilities to delegate to Accounting. Instead, Boss called them separately. The payment was correct, but Facilities made the cash calculation mistake mentioned earlier. Accounting and Boss used the correct available cash figure. After my approval, the remaining checking balance was $160, exactly as we expected.
>
> For ticket 103, I expected Inventory to work with Accounting before Customer Service prepared the draft. But again, Boss delegated directly to the specialists, and some work was happening in parallel. Accounting mainly checked the 10% discount instead of comparing several options. Also, Customer Service made a mistake in the draft which required my correction.
>
> Overall, all three tickets were marked resolved, but the actual delegation structure was different from our plans. Even though we gave full connectivity to the agents, most of the coordination still happened through Boss. The financial results matched: $3,400 starting cash minus $840 invoice and $2,400 rent equals $160 ending cash. The agents did not approve their own payments.
>
> 3. What would have been simpler with one agent with tools, and why?
>
> I think some tasks could have been easier with just one agent. For example, ticket 102 was quite straightforward. We only needed to verify the lease, check the cash balance, prepare the rent payment and wait for human approval. Instead, Boss had to communicate with Facilities and Accounting separately. This used 13 model requests and 17 tool calls. One agent with access to check_rent_notice, get_cash_position and request_rent_payment could probably do the same work with fewer calls and tokens.
>
> The stock check in ticket 101 and the discount calculation in ticket 103 were also relatively simple. However, I still think the multi-agent approach is useful for more complicated cases because each agent has its own responsibility. Inventory focuses on stock, Accounting looks at financial feasibility and Customer Service prepares communication. I would probably use one agent for simple requests and multiple agents for more complicated decisions. I would still keep human approval for payments in both cases.
>
> 4. Describe three new problems Campus Customs might face that this agent team could solve with existing tools.
>
> First, a customer might ask whether we have three Bulldog tees in size M. We know there are five in stock from our database. Inventory could check the quantity using get_inventory, and Customer Service could prepare a response using save_customer_message_draft. We could answer the customer without adding new tools.
>
> Second, Campus Customs could receive another rent reminder for October. After our September payment, the next rent is due October 2, but we only have $160. Facilities could check the lease, while Accounting could check the cash and explain that we don't have enough money to pay $2,400. The system could identify the problem and avoid an incorrect payment, even though it cannot generate more cash.
>
> Third, another student club might ask for a discount on 10 size L navy hoodies. We already have 14 units in stock. Inventory could verify this, Accounting could use check_discount to test a proposed price against the $22 unit cost, and Customer Service could prepare a draft. Boss could then leave the final discount decision for human review.
>
> 5. Describe three new problems the agents could not solve with existing tools, and what new tools or agents would be needed.
>
> First, the agents cannot really track shipping and delivery. For ticket 101 we know Bulldog Print Co has a five-day lead time, but we don't know whether the size S tees were actually shipped or when they will arrive. We would need a Shipping or Logistics agent and new MCP tools to check shipping status, tracking numbers and confirmed delivery dates.
>
> Second, the agents cannot actually complete a customer sale and receive money. For ticket 103, we approved a 10% discount for eight hoodies, but our database doesn't model incoming revenue, customer payments or completed sales. The eight hoodies are still in inventory. We would need a Sales or Checkout agent connected to payment processing, customer orders and inventory updates. This would allow us to record the $417.60 sale if Yale AI Club accepts the offer.
>
> Third, the agents cannot find and negotiate with new suppliers. Currently we only have Bulldog Print Co as our apparel supplier, and its unpaid invoice blocked restocking. If we wanted to compare other suppliers, our existing tools would not be enough. We would need a Procurement agent with tools to search for suppliers, get quotations, compare prices and negotiate delivery terms. Any actual purchase should still require human approval.
>
> Overall reflection
>
> I think this project showed that multi-agent systems can be useful when several different business functions need to work together. The agents were able to understand our inventory, invoices, rent and financial constraints and prepare reasonable actions. However, I also saw that adding more agents doesn't automatically make the process better. Sometimes it increases token usage and creates communication problems. We also saw mistakes in cash calculation and customer messaging. For me, the most important part is having reliable MCP tools, clear responsibilities, good audit trail and human approval for important decisions, rather than simply having many agents.

---

## Problem 11: Prepare the repository for GitHub

### Prompt 1

> We are almost done with HW5. Before uploading to GitHub, I found some missing files in the project root. Please create .gitignore to exclude .env, .venv, node_modules, build files and Python cache, but keep both database files and all output results and screenshots. Create .env.example with PORTKEY_API_KEY placeholder, and root requirements.txt with all Python dependencies. Also create a root README.md with clear steps to install dependencies, set up the API key, start MCP, FastAPI backend and React frontend, and reset the database if needed. Our .mcp.json currently has absolute Windows paths from my computer, so make it portable for someone cloning the repository. Make sure no real API keys or local virtual environment files are included in Git. Do not reset the databases, rerun agents, or change any results. Keep this simple and quick. Add this prompt to AI_prompts.md under Problem 11. Don't push to GitHub yet.

### Follow-up prompt 1

**What was missing:** The project was ready but not yet on GitHub. This step created the public repository `hw5-campus-customs` with GitHub CLI and pushed the complete project. Before pushing, it checked that `.env`, `.venv`, `node_modules`, caches and build files were excluded. The repository URL is saved in `output/github_url.txt`.

> Now let's finish Problem 11: Submit to GitHub. Please create a new public GitHub repository called hw5-campus-customs and upload our complete HW5 project there. Use GitHub CLI if available. Before pushing, check that .env, .venv, node_modules, caches and build files are not included, but both databases, all source code, AI_prompts.md, output files and screenshots are included. Don't reset the database or run the agents again. Make the commit and push everything to GitHub. Then verify that the repository is public and all required files are there. Save the actual repository URL in output/github_url.txt and make sure this file is also pushed. Add this prompt to AI_prompts.md under Problem 11 before committing. If GitHub authentication is needed, tell me what I need to do. Don't create another repository if one already exists for this project. Give me the final GitHub URL when done.

### Follow-up prompt 2

**What was missing:** The professor's expected project folder is called `hw5`, but the repository was named `hw5-campus-customs`. The same repository was renamed to `hw5` with GitHub CLI (`gh repo rename`), with no new repository and no code changes. The Git remote and `output/github_url.txt` now point to https://github.com/BeckJamilov/hw5. The older mentions of `hw5-campus-customs` above are left as the record of what happened at that step.

> One last small change before submission. The professor's expected project folder is called hw5, so I want to match it exactly. Please rename my existing public GitHub repository from hw5-campus-customs to hw5 using GitHub CLI. Do not create a new repository and don't change the project structure or any code. Update the Git remote, output/github_url.txt and any references to the old GitHub URL, then commit and push the changes. Make sure the new repository is public and all files are still there. Don't reset the database or run the agents again. Give me the new URL when finished.
